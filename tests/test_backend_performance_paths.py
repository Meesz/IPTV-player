"""Behaviour tests for the optimized EPG parsing and Xtream channel mapping paths."""

import gc
import gzip
from datetime import UTC, datetime, timedelta

import pytest

from core.models import XtreamCredentials
from infra.parsers.epg_parser import EPGParser
from infra.providers.xtream_client import XtreamClient

# --- parse_date ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("20240115103000", datetime(2024, 1, 15, 10, 30, 0, tzinfo=UTC)),
        ("202401151030", datetime(2024, 1, 15, 10, 30, 0, tzinfo=UTC)),
        ("20240115103000Z", datetime(2024, 1, 15, 10, 30, 0, tzinfo=UTC)),
        ("  20240115103000  ", datetime(2024, 1, 15, 10, 30, 0, tzinfo=UTC)),
        ("20240115103000 +0100", datetime(2024, 1, 15, 9, 30, 0, tzinfo=UTC)),
        ("20240115103000+0100", datetime(2024, 1, 15, 9, 30, 0, tzinfo=UTC)),
        ("20240115103000 +01:00", datetime(2024, 1, 15, 9, 30, 0, tzinfo=UTC)),
        ("20240115103000 -0530", datetime(2024, 1, 15, 16, 0, 0, tzinfo=UTC)),
        ("202401151030 +0200", datetime(2024, 1, 15, 8, 30, 0, tzinfo=UTC)),
        ("20240115103000 +0100 trailing", datetime(2024, 1, 15, 9, 30, 0, tzinfo=UTC)),
        ("20240115103000garbage", datetime(2024, 1, 15, 10, 30, 0, tzinfo=UTC)),
        ("2024011510300", datetime(2024, 1, 15, 10, 30, 0, tzinfo=UTC)),
        ("20240229235959", datetime(2024, 2, 29, 23, 59, 59, tzinfo=UTC)),
        ("20240101000000 +0100", datetime(2023, 12, 31, 23, 0, 0, tzinfo=UTC)),
    ],
)
def test_parse_date_accepted_inputs(raw, expected):
    parsed = EPGParser.parse_date(raw)

    assert parsed == expected
    assert parsed.utcoffset() == timedelta(0)


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "   ",
        "abc",
        "2024",
        "20240115",
        "2024011510",
        "20230229120000",  # not a leap year
        "20240230120000",
        "".join(chr(0xFF10 + int(d)) for d in "20240115103000"),  # full-width digits
        "20241301120000",
        "20240100120000",
        "20240132120000",
        "20240115240000",
        "20240115106000",
        "20240115103060",
        "00000115103000",
        "20240115103000 +9999",
    ],
)
def test_parse_date_rejected_inputs_raise_value_error(raw):
    with pytest.raises(ValueError):
        EPGParser.parse_date(raw)


def test_parse_date_error_messages_are_stable():
    with pytest.raises(ValueError, match="Empty date"):
        EPGParser.parse_date("")
    with pytest.raises(ValueError, match="Unsupported date format: nope"):
        EPGParser.parse_date("nope")
    with pytest.raises(ValueError, match=r"day .*(range|month)"):
        EPGParser.parse_date("20240230120000")


def test_parse_date_matches_strptime_for_random_valid_dates():
    for year, month, day, hour, minute, second in [
        (1999, 12, 31, 23, 59, 59),
        (2000, 2, 29, 0, 0, 0),
        (2026, 10, 18, 12, 5, 9),
    ]:
        raw = f"{year:04}{month:02}{day:02}{hour:02}{minute:02}{second:02}"
        expected = datetime.strptime(raw, "%Y%m%d%H%M%S").replace(tzinfo=UTC)
        assert EPGParser.parse_date(raw) == expected


# --- EPG parsing --------------------------------------------------------------------------

_XMLTV = """<?xml version="1.0" encoding="UTF-8"?>
<tv>
  <channel id="a"><display-name>A</display-name></channel>
  <programme start="20240115100000 +0000" stop="20240115110000 +0000" channel="a">
    <title>First</title><desc>Desc one</desc><category>News</category>
  </programme>
  <programme start="bogus" stop="20240115110000 +0000" channel="a"><title>Bad</title></programme>
  <programme start="20240115110000 +0000" stop="20240115120000 +0000" channel="b">
    <title>Second</title>
  </programme>
  <programme start="20240115110000 +0000" stop="20240115120000 +0000" channel="b">
    <title>Second replaced</title>
  </programme>
</tv>
"""


def _write(tmp_path, content, name="epg.xml"):
    path = tmp_path / name
    if isinstance(content, str):
        content = content.encode("utf-8")
    path.write_bytes(content)
    return str(path)


def test_epg_parse_keeps_order_warnings_and_content(tmp_path):
    channels, warnings = EPGParser.parse_with_warnings(_write(tmp_path, _XMLTV))

    assert list(channels) == ["a", "b"]
    first = channels["a"].programs[0]
    assert (first.title, first.description, first.category) == ("First", "Desc one", "News")
    assert [p.title for p in channels["b"].programs] == ["Second replaced"]
    assert [w.code for w in warnings] == ["invalid_program_date", "duplicate_programme"]


def test_epg_parse_handles_namespaced_xmltv(tmp_path):
    xml = (
        '<x:tv xmlns:x="urn:example"><x:programme start="20240115100000" stop="20240115110000" channel="n">'
        "<x:title>Namespaced</x:title></x:programme></x:tv>"
    )

    channels = EPGParser.parse(_write(tmp_path, xml))

    assert channels["n"].programs[0].title == "Namespaced"


def test_epg_parse_finds_programmes_inside_wrapper_elements(tmp_path):
    xml = (
        "<tv>"
        '<x><programme start="20240115100000" stop="20240115110000" channel="w"><title>One</title></programme>'
        '<programme start="20240115110000" stop="20240115120000" channel="w"><title>Two</title></programme></x>'
        '<programme start="20240115120000" stop="20240115130000" channel="w"><title>Three</title></programme>'
        "</tv>"
    )

    channels = EPGParser.parse(_write(tmp_path, xml))

    assert [p.title for p in channels["w"].programs] == ["One", "Two", "Three"]


def test_epg_parse_wrong_root_raises_before_any_programme_warning(tmp_path, caplog):
    xml = '<other><programme start="bogus" stop="bogus" channel="a"/></other>'

    with caplog.at_level("WARNING"), pytest.raises(ValueError, match="missing root 'tv'"):
        EPGParser.parse(_write(tmp_path, xml))

    assert "invalid date" not in caplog.text


def test_parse_date_timezone_cache_stays_bounded():
    from infra.parsers import epg_parser

    epg_parser._TZ_CACHE.clear()
    # Equal offsets in different spellings must share one cache entry (keyed by offset, not text).
    fullwidth = "".join(chr(0xFF10 + int(d)) for d in "0100")  # full-width digits
    for spelling in ("+0100", "+01:00", f"+{fullwidth}", f"+{fullwidth[:2]}:{fullwidth[2:]}"):
        EPGParser.parse_date(f"20240115103000{spelling}")
    assert list(epg_parser._TZ_CACHE) == [60]

    EPGParser.parse_date("20240115103000-0100")
    assert sorted(epg_parser._TZ_CACHE) == [-60, 60]


def test_epg_parse_reads_gzip(tmp_path):
    path = _write(tmp_path, gzip.compress(_XMLTV.encode("utf-8")), "epg.xml.gz")

    assert list(EPGParser.parse(path)) == ["a", "b"]


def test_epg_parse_rejects_wrong_root(tmp_path):
    xml = '<other><programme start="20240115100000" stop="20240115110000" channel="a"/></other>'

    with pytest.raises(ValueError, match="missing root 'tv'"):
        EPGParser.parse(_write(tmp_path, xml))


def test_epg_parse_reports_malformed_xml_as_value_error(tmp_path):
    xml = _XMLTV.replace("</tv>", "")

    with pytest.raises(ValueError, match="Malformed XML in EPG file"):
        EPGParser.parse(_write(tmp_path, xml))


def test_epg_parse_without_programmes_raises(tmp_path):
    with pytest.raises(ValueError, match="No programs found"):
        EPGParser.parse(_write(tmp_path, "<tv><channel id='a'/></tv>"))


def test_epg_parse_enforces_decompression_limit(tmp_path, monkeypatch):
    monkeypatch.setattr("infra.parsers.epg_parser.limits.MAX_EPG_DECOMPRESSED_BYTES", 64)
    path = _write(tmp_path, gzip.compress(_XMLTV.encode("utf-8")), "epg.xml.gz")

    with pytest.raises(ValueError, match="exceeds"):
        EPGParser.parse(path)


@pytest.mark.parametrize("initially_enabled", [True, False])
def test_epg_parse_restores_gc_state(tmp_path, initially_enabled):
    path = _write(tmp_path, _XMLTV)
    was_enabled = gc.isenabled()
    try:
        gc.enable() if initially_enabled else gc.disable()
        EPGParser.parse(path)
        assert gc.isenabled() is initially_enabled
    finally:
        gc.enable() if was_enabled else gc.disable()


def test_epg_parse_restores_gc_state_on_error(tmp_path):
    path = _write(tmp_path, _XMLTV.replace("</tv>", ""))
    was_enabled = gc.isenabled()
    try:
        gc.enable()
        with pytest.raises(ValueError):
            EPGParser.parse(path)
        assert gc.isenabled() is True
    finally:
        gc.enable() if was_enabled else gc.disable()


# --- Xtream live channel mapping ----------------------------------------------------------


def _fetch_channels(monkeypatch, credentials, streams):
    client = XtreamClient()
    monkeypatch.setattr(client, "fetch_live_categories", lambda creds: {"1": "News"})
    monkeypatch.setattr(client, "_request_json", lambda creds, params: streams)
    return client.fetch_live_channels(credentials)


@pytest.mark.parametrize(
    ("server", "expected_base"),
    [
        ("http://host.example", "http://host.example"),
        ("https://host.example/", "https://host.example"),
        ("http://host.example:8080", "http://host.example:8080"),
        ("http://host.example:8080/panel/", "http://host.example:8080/panel"),
    ],
)
def test_xtream_live_urls_are_unchanged(monkeypatch, server, expected_base):
    credentials = XtreamCredentials(server, " us er ", " p@ss/w:rd ", " M3U8 ")
    streams = [
        {"stream_id": 12, "name": "One", "category_id": "1", "num": "3", "epg_channel_id": "one.uk"},
        {"stream_id": " a/b ", "name": "Two"},
        {"stream_id": "", "name": "Skipped"},
        {"stream_id": 5, "name": "Movie", "stream_type": "movie"},
    ]

    channels = _fetch_channels(monkeypatch, credentials, streams)

    assert [c.name for c in channels] == ["One", "Two"]
    assert channels[0].url == f"{expected_base}/live/us%20er/p%40ss%2Fw%3Ard/12.m3u8"
    assert channels[1].url == f"{expected_base}/live/us%20er/p%40ss%2Fw%3Ard/a%2Fb.m3u8"
    assert channels[0].url == XtreamClient._build_live_stream_url(credentials, "12")
    assert (channels[0].group, channels[0].epg_id, channels[0].channel_number) == ("News", "one.uk", 3)


def test_xtream_mapping_does_not_log_stream_urls_or_passwords(monkeypatch, caplog):
    credentials = XtreamCredentials("http://host.example", "user", "s3cret-pass", "ts")

    with caplog.at_level("DEBUG"):
        _fetch_channels(monkeypatch, credentials, [{"stream_id": 1, "name": "One"}])

    assert "s3cret-pass" not in caplog.text
    assert "/live/" not in caplog.text
