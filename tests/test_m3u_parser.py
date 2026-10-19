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


def _write_bytes(tmp_path, payload: bytes):
    playlist_path = tmp_path / "sample.m3u"
    playlist_path.write_bytes(payload)
    return playlist_path


def test_cp1252_playlist_parses_regardless_of_byte_length_parity(tmp_path):
    """BOM-less single-byte text must not be mis-decoded as UTF-16 when even length."""
    # The euro sign (0x80) only decodes correctly as cp1252 (latin-1 gives a control char).
    base = "#EXTM3U\n#EXTINF:-1,Café € TV\nhttp://example.com/a"
    payloads = [text.encode("cp1252") for text in (base, base + "\n")]
    assert {len(payload) % 2 for payload in payloads} == {0, 1}
    for payload in payloads:
        parsed = M3UParser.parse(str(_write_bytes(tmp_path, payload)))
        assert [channel.name for channel in parsed.channels] == ["Café € TV"]


def test_utf16_playlist_with_bom_parses(tmp_path):
    text = "#EXTM3U\n#EXTINF:-1,Café TV\nhttp://example.com/a\n"
    for encoding in ("utf-16", "utf-16-be"):
        payload = text.encode(encoding)
        if encoding == "utf-16-be":
            payload = b"\xfe\xff" + payload
        parsed = M3UParser.parse(str(_write_bytes(tmp_path, payload)))
        assert [channel.name for channel in parsed.channels] == ["Café TV"]


def test_unquoted_attribute_value_ends_at_title_comma(tmp_path):
    playlist_path = _write_playlist(
        tmp_path,
        [
            "#EXTM3U",
            '#EXTINF:-1 group-title="News, World" tvg-id=foo,Name',
            "http://example.com/a",
        ],
    )

    parsed = M3UParser.parse(str(playlist_path))

    assert len(parsed.channels) == 1
    assert parsed.channels[0].epg_id == "foo"
    assert parsed.channels[0].name == "Name"
    assert parsed.channels[0].group == "News, World"
