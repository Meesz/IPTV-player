"""EPG now/next from memory (EPGChannel) and the EPGService memory-vs-DB routing.

Kills M5 (the ``< end_time`` bound dropped, so a finished programme shows as live).
"""

from datetime import UTC, datetime, timedelta, timezone

from core.models import EPGChannel, Program
from core.services.epg_service import EPGService
from infra.db.epg_repository import EPGRepository
from infra.db.sqlite_connection import SQLiteConnection

T10 = datetime(2026, 4, 1, 10, 0, tzinfo=UTC)
T11 = datetime(2026, 4, 1, 11, 0, tzinfo=UTC)
T12 = datetime(2026, 4, 1, 12, 0, tzinfo=UTC)
T13 = datetime(2026, 4, 1, 13, 0, tzinfo=UTC)
T14 = datetime(2026, 4, 1, 14, 0, tzinfo=UTC)


def _channel() -> EPGChannel:
    return EPGChannel(
        channel_id="news",
        programs=[
            Program(title="Old show", start_time=T10, end_time=T11),
            Program(title="Current show", start_time=T11, end_time=T12),
            Program(title="Next show", start_time=T12, end_time=T13),
        ],
    )


def test_current_program_includes_start_instant():
    assert _channel().get_current_program(T11).title == "Current show"


def test_current_program_in_the_middle():
    assert _channel().get_current_program(T11 + timedelta(minutes=30)).title == "Current show"


def test_current_program_excludes_end_instant_and_hands_over_to_next():
    # 12:00 is the end of "Current show" (exclusive) and the start of "Next show".
    assert _channel().get_current_program(T12).title == "Next show"


def test_current_program_is_none_after_the_last_programme_ended():
    assert _channel().get_current_program(T13) is None
    assert _channel().get_current_program(T14) is None


def test_stale_programme_is_not_shown_as_current_when_nothing_else_airs():
    channel = EPGChannel(channel_id="x", programs=[Program(title="Old show", start_time=T10, end_time=T11)])

    assert channel.get_current_program(T12) is None


def test_current_program_is_none_before_the_first_programme():
    assert _channel().get_current_program(T10 - timedelta(seconds=1)) is None


def test_naive_datetime_is_treated_as_utc():
    naive = datetime(2026, 4, 1, 11, 30)

    assert _channel().get_current_program(naive).title == "Current show"
    assert _channel().get_current_program(datetime(2026, 4, 1, 13, 0)) is None


def test_aware_datetime_in_other_timezone_is_compared_by_instant():
    plus_two = timezone(timedelta(hours=2))
    local = datetime(2026, 4, 1, 13, 30, tzinfo=plus_two)  # 11:30 UTC

    assert _channel().get_current_program(local).title == "Current show"


def test_upcoming_programs_are_ordered_and_exclude_current():
    channel = EPGChannel(
        channel_id="news",
        programs=[
            Program(title="Third", start_time=T13, end_time=T14),
            Program(title="Current", start_time=T10, end_time=T12),
            Program(title="Second", start_time=T12, end_time=T13),
        ],
    )

    upcoming = channel.get_upcoming_programs(T11)

    assert [program.title for program in upcoming] == ["Second", "Third"]


def test_upcoming_programs_respect_limit():
    channel = EPGChannel(
        channel_id="news",
        programs=[
            Program(title=f"P{hour}", start_time=T10 + timedelta(hours=hour), end_time=T11 + timedelta(hours=hour))
            for hour in range(1, 6)
        ],
    )

    assert [p.title for p in channel.get_upcoming_programs(T10, limit=2)] == ["P1", "P2"]
    assert len(channel.get_upcoming_programs(T10)) == 5
    assert channel.get_upcoming_programs(T10, limit=0) == []


def test_upcoming_programs_do_not_include_a_programme_starting_exactly_now():
    assert [p.title for p in _channel().get_upcoming_programs(T11)] == ["Next show"]


XMLTV = """<tv>
  <programme channel="news.us" start="20260401100000 +0000" stop="20260401110000 +0000">
    <title>Old show</title>
  </programme>
  <programme channel="news.us" start="20260401110000 +0000" stop="20260401120000 +0000">
    <title>Current show</title>
    <desc>Live now</desc>
  </programme>
  <programme channel="news.us" start="20260401120000 +0000" stop="20260401130000 +0000">
    <title>Next show</title>
  </programme>
</tv>
"""


def _write_xmltv(tmp_path):
    path = tmp_path / "guide.xml"
    path.write_text(XMLTV, encoding="utf-8")
    return path


def test_load_epg_from_path_populates_channels_and_serves_from_memory(tmp_path):
    db = SQLiteConnection(db_path=tmp_path / "app.sqlite")
    repository = EPGRepository(db)
    service = EPGService(repository)
    assert service.loaded_channels == []

    service.load_epg_from_path(str(_write_xmltv(tmp_path)))
    # Wipe the DB cache: an answer can now only come from memory.
    repository.clear()

    assert service.loaded_channels == ["news.us"]
    assert service.get_program_for_channel("news.us", current_time=T11 + timedelta(minutes=5)).title == "Current show"
    assert service.get_program_for_channel("news.us", current_time=T13) is None
    assert [p.title for p in service.get_upcoming_programs("news.us", current_time=T11)] == ["Next show"]


def test_fresh_service_falls_back_to_database_cache(tmp_path):
    db = SQLiteConnection(db_path=tmp_path / "app.sqlite")
    EPGService(EPGRepository(db)).load_epg_from_path(str(_write_xmltv(tmp_path)))

    restarted = EPGService(EPGRepository(db))

    assert restarted.loaded_channels == []
    current = restarted.get_program_for_channel("news.us", current_time=T11 + timedelta(minutes=5))
    assert current is not None
    assert current.title == "Current show"
    assert current.description == "Live now"
    assert restarted.get_program_for_channel("news.us", current_time=T13) is None
    assert [p.title for p in restarted.get_upcoming_programs("news.us", current_time=T11)] == ["Next show"]


def test_channel_missing_from_memory_is_looked_up_in_database(tmp_path):
    db = SQLiteConnection(db_path=tmp_path / "app.sqlite")
    repository = EPGRepository(db)
    service = EPGService(repository)
    service.load_epg_from_path(str(_write_xmltv(tmp_path)))
    repository.save_program("other", Program(title="Cached only", start_time=T10, end_time=T12))

    assert service.get_program_for_channel("other", current_time=T11).title == "Cached only"
    assert service.get_program_for_channel("unknown", current_time=T11) is None
