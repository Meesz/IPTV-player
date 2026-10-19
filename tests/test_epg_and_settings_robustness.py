"""Low-severity correctness alignments (Qt-free).

1. EPGRepository.get_upcoming_programs must exclude the currently-airing
   program so it matches the in-memory EPGChannel path and is not duplicated
   with the now-playing view after a restart (DB-cache path).
2. PlaylistReference.from_settings_value must degrade gracefully on an
   unrecognized source_type instead of raising ValueError.
"""

import json
import re
from datetime import UTC, datetime

import pytest

from core.errors import ParsingError
from core.models import EPGChannel, PlaylistReference, PlaylistSourceType, Program
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


def test_from_settings_value_degrades_on_unknown_source_type():
    reference = PlaylistReference.from_settings_value(
        json.dumps({"source_type": "bogus", "path": "https://example.com/list.m3u"})
    )

    assert reference is not None
    assert reference.source_type == PlaylistSourceType.URL
    assert reference.path == "https://example.com/list.m3u"


def test_from_settings_value_unknown_type_file_path_defaults_to_file():
    reference = PlaylistReference.from_settings_value(
        json.dumps({"source_type": "future_kind", "path": "/tmp/list.m3u"})
    )

    assert reference is not None
    assert reference.source_type == PlaylistSourceType.FILE


def test_from_settings_value_still_reads_known_types():
    reference = PlaylistReference.from_settings_value(
        json.dumps({"source_type": "url", "path": "https://example.com/list.m3u"})
    )

    assert reference is not None
    assert reference.source_type == PlaylistSourceType.URL


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
