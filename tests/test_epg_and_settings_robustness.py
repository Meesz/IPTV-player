"""EPG cache correctness (Qt-free).

1. EPGRepository.get_upcoming_programs must exclude the currently-airing
   program so it matches the in-memory EPGChannel path and is not duplicated
   with the now-playing view after a restart (DB-cache path).
2. A second guide load must replace the SQLite guide cache, and a load cancelled
   after parsing must leave the previous cache intact.
"""

import re
from concurrent.futures import CancelledError
from datetime import UTC, datetime

import pytest

from core.errors import ParsingError
from core.models import EPGChannel, Program
from core.services.epg_service import EPGService
from infra.db.epg_repository import EPGRepository
from infra.db.sqlite_connection import SQLiteConnection

_NOW = datetime(2026, 4, 1, 10, 30, tzinfo=UTC)
_AIRING = Program(
    title="Now Airing",
    start_time=datetime(2026, 4, 1, 10, 0, tzinfo=UTC),
    end_time=datetime(2026, 4, 1, 11, 0, tzinfo=UTC),
)
_FUTURE = Program(
    title="Later",
    start_time=datetime(2026, 4, 1, 11, 0, tzinfo=UTC),
    end_time=datetime(2026, 4, 1, 12, 0, tzinfo=UTC),
)


def test_db_upcoming_excludes_currently_airing_and_matches_memory(tmp_path):
    connection = SQLiteConnection(db_path=tmp_path / "epg.sqlite")
    repository = EPGRepository(connection)
    repository.save_all({"news.us": [_AIRING, _FUTURE]})

    db_upcoming = [p.title for p in repository.get_upcoming_programs("news.us", limit=5, current_time=_NOW)]
    memory_upcoming = [
        p.title
        for p in EPGChannel(channel_id="news.us", programs=[_AIRING, _FUTURE]).get_upcoming_programs(
            current_time=_NOW, limit=5
        )
    ]

    assert db_upcoming == ["Later"]
    assert db_upcoming == memory_upcoming


def _epg_service(tmp_path):
    return EPGService(EPGRepository(SQLiteConnection(db_path=tmp_path / "epg.sqlite")))


def test_save_all_same_key_programs_keeps_later(tmp_path):
    repository = EPGRepository(SQLiteConnection(db_path=tmp_path / "epg.sqlite"))
    start = datetime(2026, 4, 1, 10, 0, tzinfo=UTC)
    end = datetime(2026, 4, 1, 11, 0, tzinfo=UTC)

    repository.save_all(
        {
            "news.us": [
                Program(title="First", start_time=start, end_time=end),
                Program(title="Second", start_time=start, end_time=end),
            ]
        }
    )

    current = repository.get_current_program("news.us", current_time=_NOW)
    assert current is not None
    assert current.title == "Second"


def test_load_epg_with_duplicate_programmes_succeeds_and_warns(tmp_path):
    xml_path = tmp_path / "guide.xml"
    xml_path.write_text(
        '<tv><programme start="20260401100000 +0000" stop="20260401110000 +0000" channel="a">'
        "<title>First</title></programme>"
        '<programme start="20260401110000 +0000" stop="20260401120000 +0000" channel="a">'
        "<title>Middle</title></programme>"
        '<programme start="20260401100000 +0000" stop="20260401110000 +0000" channel="a">'
        "<title>Second</title></programme></tv>",
        encoding="utf-8",
    )
    service = _epg_service(tmp_path)

    service.load_epg_from_path(str(xml_path))

    current = service.get_program_for_channel("a", current_time=_NOW)
    assert current is not None
    assert current.title == "Second"
    assert [p.title for p in service._channels["a"].programs] == ["Second", "Middle"]
    duplicate_warnings = [w for w in service.last_warnings if w.code == "duplicate_programme"]
    assert len(duplicate_warnings) == 1
    assert "Replaced 1 duplicate" in duplicate_warnings[0].message


def test_load_epg_malformed_xml_raises_parsing_error(tmp_path):
    xml_path = tmp_path / "broken.xml"
    xml_path.write_text("<tv><programme channel='a'></tv>", encoding="utf-8")

    with pytest.raises(ParsingError) as exc_info:
        _epg_service(tmp_path).load_epg_from_path(str(xml_path))

    assert re.search(r"line \d+, column \d+", str(exc_info.value.__cause__))


def _write_guide(path, channel_id: str, title: str):
    path.write_text(
        f'<tv><programme start="20260401100000 +0000" stop="20260401110000 +0000" channel="{channel_id}">'
        f"<title>{title}</title></programme></tv>",
        encoding="utf-8",
    )
    return str(path)


def test_second_guide_load_replaces_cached_guide(tmp_path):
    guide_a = _write_guide(tmp_path / "a.xml", "a", "Guide A")
    guide_b = _write_guide(tmp_path / "b.xml", "b", "Guide B")
    service = _epg_service(tmp_path)

    service.load_epg_from_path(guide_a)
    service.load_epg_from_path(guide_b)

    # A fresh repository reads only what was persisted, as after a restart.
    repository = EPGRepository(SQLiteConnection(db_path=tmp_path / "epg.sqlite"))
    assert repository.get_current_program("a", current_time=_NOW) is None
    current_b = repository.get_current_program("b", current_time=_NOW)
    assert current_b is not None
    assert current_b.title == "Guide B"


def test_guide_load_cancelled_after_parse_keeps_previous_cache(tmp_path):
    guide_a = _write_guide(tmp_path / "a.xml", "a", "Guide A")
    guide_b = _write_guide(tmp_path / "b.xml", "b", "Guide B")
    service = _epg_service(tmp_path)
    service.load_epg_from_path(guide_a)

    # Cancelled once parsing is under way, i.e. superseded before the cache save.
    progress: list[str] = []
    with pytest.raises(CancelledError):
        service.load_epg_from_path(
            guide_b,
            progress_callback=progress.append,
            cancel_callback=lambda: "Parsing EPG data" in progress,
        )

    repository = EPGRepository(SQLiteConnection(db_path=tmp_path / "epg.sqlite"))
    current_a = repository.get_current_program("a", current_time=_NOW)
    assert current_a is not None
    assert current_a.title == "Guide A"
    assert repository.get_current_program("b", current_time=_NOW) is None
    assert service.get_program_for_channel("a", current_time=_NOW) is not None


def test_guide_load_cancelled_during_cache_save_keeps_previous_cache(tmp_path):
    guide_a = _write_guide(tmp_path / "a.xml", "a", "Guide A")
    guide_b = _write_guide(tmp_path / "b.xml", "b", "Guide B")
    service = _epg_service(tmp_path)
    service.load_epg_from_path(guide_a)

    # Superseded after the pre-save check passed: the save must roll back, not commit.
    progress: list[str] = []
    with pytest.raises(CancelledError):
        service.load_epg_from_path(
            guide_b,
            progress_callback=progress.append,
            cancel_callback=lambda: "Saving EPG cache" in progress,
        )

    repository = EPGRepository(SQLiteConnection(db_path=tmp_path / "epg.sqlite"))
    current_a = repository.get_current_program("a", current_time=_NOW)
    assert current_a is not None
    assert current_a.title == "Guide A"
    assert repository.get_current_program("b", current_time=_NOW) is None


def test_save_all_stops_inserting_once_cancelled(tmp_path, monkeypatch):
    monkeypatch.setattr("infra.db.epg_repository.SAVE_CHUNK_ROWS", 2)
    repository = EPGRepository(SQLiteConnection(db_path=tmp_path / "epg.sqlite"))
    repository.save_all({"a": [_AIRING]})
    stale = {f"ch{i}": [_AIRING] for i in range(10)}
    checks = 0

    def cancelled() -> bool:
        nonlocal checks
        checks += 1
        return checks > 2

    # A stale save holds the SQLite write lock, so it must give it up early.
    with pytest.raises(CancelledError):
        repository.save_all(stale, cancel_callback=cancelled)

    assert checks == 3
    assert repository.get_current_program("a", current_time=_NOW) is not None
    assert repository.get_current_program("ch0", current_time=_NOW) is None
