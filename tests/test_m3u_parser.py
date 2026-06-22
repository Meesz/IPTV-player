"""Regression tests for the M3U parser duration handling.

These tests intentionally avoid importing PyQt6 so they run even when the Qt
runtime is unavailable (e.g. on Python versions without PyQt6 wheels). They
guard the fix that stopped the parser from silently dropping channels whose
``#EXTINF`` duration was anything other than the literal ``-1``.
"""

from infra.parsers.m3u_parser import M3UParser


def _write_playlist(tmp_path, lines):
    playlist_path = tmp_path / "sample.m3u"
    playlist_path.write_text("\n".join(lines), encoding="utf-8")
    return playlist_path


def test_parses_non_negative_one_durations(tmp_path):
    """Channels with real/zero/float durations must not be dropped."""
    playlist_path = _write_playlist(
        tmp_path,
        [
            "#EXTM3U",
            '#EXTINF:120 tvg-id="a" group-title="VOD",Movie A',
            "http://example.com/a",
            "#EXTINF:0,Channel B",
            "http://example.com/b",
            '#EXTINF:-1 tvg-id="c" group-title="Live",Channel C',
            "http://example.com/c",
            "#EXTINF:7200.5,Long Show",
            "http://example.com/d",
            "#EXTINF:-1.0,Also Live",
            "http://example.com/e",
        ],
    )

    parsed = M3UParser.parse(str(playlist_path))

    assert [channel.name for channel in parsed.channels] == [
        "Movie A",
        "Channel B",
        "Channel C",
        "Long Show",
        "Also Live",
    ]
    assert parsed.channels[0].group == "VOD"
    # None of these well-formed entries should be reported as malformed.
    assert not any(warning.code == "invalid_extinf" for warning in parsed.parse_warnings)


def test_tolerates_whitespace_after_colon(tmp_path):
    playlist_path = _write_playlist(
        tmp_path,
        [
            "#EXTM3U",
            '#EXTINF: -1 tvg-id="a",Spaced Live',
            "http://example.com/a",
        ],
    )

    parsed = M3UParser.parse(str(playlist_path))

    assert len(parsed.channels) == 1
    assert parsed.channels[0].name == "Spaced Live"


def test_still_warns_on_missing_duration(tmp_path):
    """A genuinely malformed EXTINF (no numeric duration) is still skipped."""
    playlist_path = _write_playlist(
        tmp_path,
        [
            "#EXTM3U",
            "#EXTINF:,No Duration",
            "http://example.com/bad",
            "#EXTINF:-1,Good Channel",
            "http://example.com/good",
        ],
    )

    parsed = M3UParser.parse(str(playlist_path))

    assert [channel.name for channel in parsed.channels] == ["Good Channel"]
    codes = {warning.code for warning in parsed.parse_warnings}
    assert "invalid_extinf" in codes
    assert "orphan_stream_url" in codes


def test_comma_inside_quoted_attribute_does_not_corrupt_name(tmp_path):
    """A comma inside group-title="News, World" must not bleed into the name."""
    playlist_path = _write_playlist(
        tmp_path,
        [
            "#EXTM3U",
            '#EXTINF:-1 tvg-id="cnn" group-title="News, World",CNN International',
            "http://example.com/cnn",
        ],
    )

    parsed = M3UParser.parse(str(playlist_path))

    assert len(parsed.channels) == 1
    assert parsed.channels[0].name == "CNN International"
    assert parsed.channels[0].group == "News, World"
    assert parsed.channels[0].epg_id == "cnn"
    assert not any(warning.code == "invalid_extinf" for warning in parsed.parse_warnings)


def test_title_may_contain_commas(tmp_path):
    """Only the first unquoted comma separates attrs from the title."""
    playlist_path = _write_playlist(
        tmp_path,
        [
            "#EXTM3U",
            "#EXTINF:-1 group-title='Sports',ESPN, HD",
            "http://example.com/espn",
        ],
    )

    parsed = M3UParser.parse(str(playlist_path))

    assert len(parsed.channels) == 1
    assert parsed.channels[0].name == "ESPN, HD"
    assert parsed.channels[0].group == "Sports"


def test_matches_existing_basic_fixture(tmp_path):
    """Mirror tests/test_models_and_services.py::test_m3u_parser_reads_channels.

    Proves the broadened regex does not regress the canonical fixture, which
    the Qt-coupled suite (and CI) also assert.
    """
    playlist_path = _write_playlist(
        tmp_path,
        [
            "#EXTM3U",
            '#EXTINF:-1 tvg-id="news.us" tvg-name="News Channel" group-title="News",News Channel',
            "http://example.com/stream/news",
        ],
    )

    parsed = M3UParser.parse(str(playlist_path))

    assert len(parsed.channels) == 1
    assert parsed.channels[0].name == "News Channel"
    assert parsed.channels[0].group == "News"


def test_matches_existing_warning_fixture(tmp_path):
    """Mirror tests/test_models_and_services.py warning fixture exactly.

    The broadened regex must keep producing the same warning codes for the
    orphan-url + invalid-numeric-attribute case.
    """
    playlist_path = _write_playlist(
        tmp_path,
        [
            "#EXTM3U",
            "http://example.com/orphan",
            "#EXTINF:-1 tvg-id='news.us' tvg-chno='not-a-number' tvg-shift='oops' group-title='News',News Channel",
            "http://example.com/stream/news",
        ],
    )

    parsed = M3UParser.parse(str(playlist_path))

    assert len(parsed.channels) == 1
    assert parsed.channels[0].name == "News Channel"
    assert parsed.channels[0].channel_number == 0
    assert parsed.channels[0].time_shift == 0
    assert {warning.code for warning in parsed.parse_warnings} == {
        "orphan_stream_url",
        "invalid_numeric_attribute",
    }
