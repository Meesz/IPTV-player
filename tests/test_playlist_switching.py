"""Playlist-switching regression coverage (Qt-free).

Guards the active-playlist transition behavior of PlaylistService: switching
sources updates current_playlist, re-tags channels with the new source-aware
identity, and a non-committing probe load never disturbs the active playlist.
This is the "playlist switching" coverage called out in docs/roadmap.md.
"""

from core.models import PlaylistReference, PlaylistSourceType
from core.services.playlist_service import PlaylistService
from infra.db.playlist_repository import PlaylistRepository
from infra.db.sqlite_connection import SQLiteConnection


def _write_playlist(path, channel_name):
    path.write_text(
        "\n".join(
            [
                "#EXTM3U",
                f'#EXTINF:-1 group-title="Group",{channel_name}',
                f"http://example.com/{channel_name.lower()}",
            ]
        ),
        encoding="utf-8",
    )
    return path


def _service(tmp_path) -> PlaylistService:
    connection = SQLiteConnection(db_path=tmp_path / "switching.sqlite")
    return PlaylistService(PlaylistRepository(connection))


def _file_identity(path) -> str:
    return PlaylistReference(name="x", path=str(path), source_type=PlaylistSourceType.FILE).source_identity


def test_switching_file_playlists_updates_current_and_retags_channels(tmp_path):
    first = _write_playlist(tmp_path / "alpha.m3u", "Alpha")
    second = _write_playlist(tmp_path / "beta.m3u", "Beta")
    service = _service(tmp_path)

    playlist_a = service.load_playlist(str(first))
    assert service.current_playlist is playlist_a
    assert [c.name for c in playlist_a.channels] == ["Alpha"]
    assert all(c.playlist_path == _file_identity(first) for c in playlist_a.channels)

    playlist_b = service.load_playlist(str(second))
    assert service.current_playlist is playlist_b
    assert [c.name for c in playlist_b.channels] == ["Beta"]
    # Channels must carry the NEW source identity, not the previous playlist's.
    assert all(c.playlist_path == _file_identity(second) for c in playlist_b.channels)
    assert playlist_b.source_path == _file_identity(second)


def test_probe_does_not_change_active_playlist(tmp_path):
    first = _write_playlist(tmp_path / "alpha.m3u", "Alpha")
    second = _write_playlist(tmp_path / "beta.m3u", "Beta")
    service = _service(tmp_path)

    service.load_playlist(str(first))
    reference = PlaylistReference(name="Beta", path=str(second), source_type=PlaylistSourceType.FILE)

    probed = service.probe_playlist_reference(reference)

    # Probe reports Beta's channel count but the active playlist stays Alpha.
    assert probed.channel_count == 1
    assert service.current_playlist is not None
    assert [c.name for c in service.current_playlist.channels] == ["Alpha"]


def test_switch_back_to_first_playlist_restores_its_channels(tmp_path):
    first = _write_playlist(tmp_path / "alpha.m3u", "Alpha")
    second = _write_playlist(tmp_path / "beta.m3u", "Beta")
    service = _service(tmp_path)

    service.load_playlist(str(first))
    service.load_playlist(str(second))
    restored = service.load_playlist(str(first))

    assert service.current_playlist is restored
    assert [c.name for c in restored.channels] == ["Alpha"]
    assert all(c.playlist_path == _file_identity(first) for c in restored.channels)
