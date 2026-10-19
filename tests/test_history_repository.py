"""History retention: recent_channels is capped to the newest entries."""

from core.models import Channel
from infra.db.history_repository import MAX_HISTORY_ENTRIES, HistoryRepository
from infra.db.sqlite_connection import SQLiteConnection


def _repository(tmp_path) -> HistoryRepository:
    return HistoryRepository(SQLiteConnection(db_path=tmp_path / "history.sqlite"))


def _channel(index: int) -> Channel:
    return Channel(name=f"Channel {index}", url=f"http://example.com/{index}")


def _count(repository: HistoryRepository) -> int:
    with repository.db.get_connection() as conn:
        return conn.execute("SELECT COUNT(*) FROM recent_channels").fetchone()[0]


def test_history_is_capped_and_keeps_newest(tmp_path):
    repository = _repository(tmp_path)
    total = MAX_HISTORY_ENTRIES + 25

    for index in range(total):
        repository.record_channel(_channel(index), "list.m3u", 1000 + index)

    assert _count(repository) == MAX_HISTORY_ENTRIES
    recent = repository.get_recent_channels(limit=MAX_HISTORY_ENTRIES + 50)
    urls = {channel.url for channel in recent}
    assert _channel(total - 1).url in urls
    assert _channel(total - MAX_HISTORY_ENTRIES).url in urls
    assert _channel(total - MAX_HISTORY_ENTRIES - 1).url not in urls
    assert recent[0].url == _channel(total - 1).url


def test_replaying_existing_channel_does_not_evict_others(tmp_path):
    repository = _repository(tmp_path)
    for index in range(MAX_HISTORY_ENTRIES):
        repository.record_channel(_channel(index), "list.m3u", 1000 + index)

    # Re-record the oldest entry: it moves to the front, nothing is evicted.
    repository.record_channel(_channel(0), "list.m3u", 5000)

    assert _count(repository) == MAX_HISTORY_ENTRIES
    recent = repository.get_recent_channels(limit=MAX_HISTORY_ENTRIES)
    assert recent[0].url == _channel(0).url
    assert {channel.url for channel in recent} == {_channel(i).url for i in range(MAX_HISTORY_ENTRIES)}


def test_recent_channels_default_limit_unchanged(tmp_path):
    repository = _repository(tmp_path)
    for index in range(20):
        repository.record_channel(_channel(index), "list.m3u", 1000 + index)

    recent = repository.get_recent_channels()

    assert len(recent) == 12
    assert recent[0].url == _channel(19).url
