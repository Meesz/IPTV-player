"""Low-severity correctness alignments (Qt-free).

1. EPGRepository.get_upcoming_programs must exclude the currently-airing
   program so it matches the in-memory EPGChannel path and is not duplicated
   with the now-playing view after a restart (DB-cache path).
2. PlaylistReference.from_settings_value must degrade gracefully on an
   unrecognized source_type instead of raising ValueError.
"""

import json
from datetime import UTC, datetime

from core.models import EPGChannel, PlaylistReference, PlaylistSourceType, Program
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
