import gc
import gzip
import logging
import os
import re
import xml.etree.ElementTree as ET
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta, timezone
from typing import Any

from core import limits
from core.models import EPGChannel, ParseWarning, Program

logger = logging.getLogger(__name__)


class _LimitedReader:
    """File-like wrapper that refuses to yield more than ``limit`` decompressed bytes."""

    def __init__(self, stream, limit: int):
        self._stream = stream
        self._limit = limit
        self._count = 0

    def read(self, size: int = -1) -> bytes:
        # Never request more than one byte past the limit so a bomb cannot inflate in memory.
        remaining = self._limit - self._count + 1
        size = remaining if size is None or size < 0 else min(size, remaining)
        data = self._stream.read(size)
        self._count += len(data)
        if self._count > self._limit:
            raise ValueError(f"Decompressed EPG data exceeds the {self._limit} byte limit")
        return data


_DATE_14_RE = re.compile(r"^(\d{14})(?:\s*([+-]\d{4}|[+-]\d{2}:\d{2}|Z))?")
_DATE_12_RE = re.compile(r"^(\d{12})(?:\s*([+-]\d{4}|[+-]\d{2}:\d{2}|Z))?")
# Keyed by the offset in minutes, which is bounded (only valid |offset| < 24h are stored).
_TZ_CACHE: dict[int, timezone] = {}


class EPGParser:
    """Parser for XMLTV EPG payloads."""

    @staticmethod
    def parse_date(date_str: str) -> datetime:
        if not date_str:
            raise ValueError("Empty date")
        normalized = date_str.strip()
        match = _DATE_14_RE.match(normalized)
        if not match:
            match = _DATE_12_RE.match(normalized)
            if not match:
                raise ValueError(f"Unsupported date format: {date_str}")

        base = match.group(1)
        tz = match.group(2)
        dt = EPGParser._naive_datetime(base)

        if not tz or tz == "Z":
            return dt.replace(tzinfo=UTC)

        normalized_tz = tz.replace(":", "")
        sign = 1 if normalized_tz.startswith("+") else -1
        offset = sign * (int(normalized_tz[1:3]) * 60 + int(normalized_tz[3:5]))
        tzinfo = _TZ_CACHE.get(offset)
        if tzinfo is None:
            tzinfo = timezone(timedelta(minutes=offset))  # raises ValueError for |offset| >= 24h
            _TZ_CACHE[offset] = tzinfo
        return dt.replace(tzinfo=tzinfo).astimezone(UTC)

    @staticmethod
    def _naive_datetime(base: str) -> datetime:
        """Build the naive datetime for a 12/14 digit string.

        Plain ASCII digits with in-range fields take a fast path. Anything else
        (non-ASCII digits, out-of-range fields) is delegated to ``strptime`` so the
        accepted inputs and the raised ``ValueError`` messages stay unchanged.
        """
        if base.isascii():
            try:
                return datetime(
                    int(base[0:4]),
                    int(base[4:6]),
                    int(base[6:8]),
                    int(base[8:10]),
                    int(base[10:12]),
                    int(base[12:14]) if len(base) == 14 else 0,
                )
            except ValueError:
                pass
        return datetime.strptime(base, "%Y%m%d%H%M") if len(base) == 12 else datetime.strptime(base, "%Y%m%d%H%M%S")

    @staticmethod
    def parse(file_path: str) -> dict[str, EPGChannel]:
        parsed, _warnings = EPGParser.parse_with_warnings(file_path)
        return parsed

    @staticmethod
    def parse_with_warnings(file_path: str) -> tuple[dict[str, EPGChannel], list[ParseWarning]]:
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"EPG file not found: {file_path}")

        if os.path.getsize(file_path) == 0:
            raise ValueError("EPG file is empty")

        # The parse allocates millions of long-lived objects and no cycles; generational GC
        # passes over them are pure overhead. Restore the caller's GC state afterwards.
        gc_was_enabled = gc.isenabled()
        gc.disable()
        try:
            return EPGParser._parse_stream(file_path)
        finally:
            if gc_was_enabled:
                gc.enable()

    @staticmethod
    def _parse_stream(file_path: str) -> tuple[dict[str, EPGChannel], list[ParseWarning]]:
        epg_data: dict[str, EPGChannel] = {}
        warnings: list[ParseWarning] = []
        seen: dict[tuple[str, int], int] = {}
        duplicates = 0
        for program in EPGParser._iter_programmes(file_path):
            channel_id = program.get("channel")
            if not channel_id:
                continue

            try:
                start_time = EPGParser.parse_date(program.get("start", ""))
                end_time = EPGParser.parse_date(program.get("stop", ""))
            except ValueError as exc:
                logger.warning("Skipping program due to invalid date (%s): %s", channel_id, exc)
                warnings.append(
                    ParseWarning(
                        code="invalid_program_date",
                        message=f"Skipped programme with invalid date for channel '{channel_id}'",
                        context=str(exc),
                    )
                )
                continue

            title = EPGParser._child_text(program, "title") or "No Title"
            description = EPGParser._child_text(program, "desc")
            category = EPGParser._child_text(program, "category")

            program_model = Program(
                title=title.strip(),
                start_time=start_time,
                end_time=end_time,
                description=(description or "").strip(),
                category=category.strip(),
            )

            channel = epg_data.setdefault(channel_id, EPGChannel(channel_id=channel_id))
            # Same key granularity as the DB (channel, whole-second UTC start):
            # a later duplicate replaces the earlier one in place.
            key = (channel_id, int(start_time.timestamp()))
            existing_index = seen.get(key)
            if existing_index is None:
                seen[key] = len(channel.programs)
                channel.programs.append(program_model)
            else:
                channel.programs[existing_index] = program_model
                duplicates += 1

        if not epg_data:
            raise ValueError("No programs found in EPG file")

        if duplicates:
            warnings.append(
                ParseWarning(
                    code="duplicate_programme",
                    message=f"Replaced {duplicates} duplicate programme(s) sharing channel and start time",
                    context=f"{duplicates} duplicate(s)",
                )
            )

        logger.info(
            "EPG loaded: %s channels, %s programs", len(epg_data), sum(len(v.programs) for v in epg_data.values())
        )
        return epg_data, warnings

    @staticmethod
    def _iter_programmes(file_path: str) -> Iterator[ET.Element]:
        """Stream ``<programme>`` elements in document order.

        Raises for a non-``tv`` root before yielding anything. Each element is cleared and
        detached once the consumer asks for the next one, so memory stays flat. Malformed
        XML is only detected when the stream reaches it, so yielded data is provisional
        until the generator is exhausted.
        """
        with open(file_path, "rb") as stream:
            signature = stream.read(2)

        try:
            if signature == b"\x1f\x8b":
                with gzip.open(file_path, "rb") as gz_stream:
                    yield from EPGParser._iter_events(_LimitedReader(gz_stream, limits.MAX_EPG_DECOMPRESSED_BYTES))
            else:
                yield from EPGParser._iter_events(file_path)
        except ET.ParseError as exc:
            line, column = exc.position
            raise ValueError(f"Malformed XML in EPG file (line {line}, column {column}): {exc}") from exc

    @staticmethod
    def _iter_events(source: Any) -> Iterator[ET.Element]:
        local_names: dict[str, str] = {}
        root: ET.Element | None = None
        for event, elem in ET.iterparse(source, events=("start", "end")):
            if event == "start":
                if root is None:
                    # The first start event is the document root.
                    root = elem
                    if EPGParser._local_name(elem.tag) != "tv":
                        raise ValueError("Invalid XMLTV format: missing root 'tv'")
                continue
            tag = elem.tag
            name = local_names.get(tag)
            if name is None:
                name = local_names[tag] = EPGParser._local_name(tag)
            if name == "programme":
                yield elem
                elem.clear()
                # Drop processed siblings (programmes, unread channels, closed wrappers) from
                # the root. Open wrappers stay reachable through the parser's own stack, so
                # later children are still attached to them and parsed.
                if root is not None:  # always true: the first start event set it
                    del root[:]

    @staticmethod
    def _local_name(tag: str) -> str:
        return tag.rsplit("}", maxsplit=1)[-1]

    @staticmethod
    def _child_text(node: ET.Element, child_name: str) -> str:
        for child in node:
            if EPGParser._local_name(child.tag) == child_name:
                return (child.text or "").strip()
        return ""
