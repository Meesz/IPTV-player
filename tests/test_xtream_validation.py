"""Negative-path tests for Xtream input validation and the auth decision.

Kills M3 (empty Xtream password accepted) and M4 (banned/disabled account accepted).
"""

import pytest
from _http import json_response

from core.errors import ParsingError, ValidationError
from core.models import PlaylistReference, PlaylistSourceType, XtreamCredentials
from core.services.playlist_service import PlaylistService
from infra.providers.xtream_client import XtreamClient


class _NoRepository:
    """Validation never touches the repository."""


def _reference(**overrides) -> PlaylistReference:
    fields = {
        "server_url": "https://provider.example",
        "username": "alice",
        "password": "secret",
        "output": "ts",
    }
    fields.update(overrides)
    return PlaylistReference(
        name="Provider",
        source_type=PlaylistSourceType.XTREAM,
        xtream=XtreamCredentials(**fields),
    )


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"server_url": ""}, "server URL is required"),
        ({"server_url": "ftp://provider.example"}, "valid http or https URL"),
        ({"username": ""}, "username is required"),
        ({"username": "   "}, "username is required"),
        ({"password": ""}, "password is required"),
        ({"password": "   "}, "password is required"),
        ({"output": "mp4"}, "output must be ts or m3u8"),
    ],
)
def test_validate_playlist_reference_rejects_bad_xtream_input(overrides, message):
    service = PlaylistService(_NoRepository())  # type: ignore[arg-type]

    with pytest.raises(ValidationError, match=message):
        service.validate_playlist_reference(_reference(**overrides))


def test_validate_playlist_reference_rejects_xtream_without_credentials():
    service = PlaylistService(_NoRepository())  # type: ignore[arg-type]
    reference = PlaylistReference(name="Provider", source_type=PlaylistSourceType.XTREAM)

    with pytest.raises(ValidationError, match="server URL is required"):
        service.validate_playlist_reference(reference)


def _validate_with_payload(monkeypatch, payload):
    """Run XtreamClient.validate_credentials against a canned authentication response."""
    client = XtreamClient()

    monkeypatch.setattr(client.session, "get", lambda *args, **kwargs: json_response(payload))
    credentials = XtreamCredentials(server_url="https://provider.example", username="alice", password="secret")
    return client.validate_credentials(credentials)


@pytest.mark.parametrize("status", ["Banned", "Disabled", "BANNED", "disabled", " Banned "])
def test_xtream_auth_rejects_banned_or_disabled_account_even_when_auth_is_set(monkeypatch, status):
    with pytest.raises(ValidationError, match="authentication failed"):
        _validate_with_payload(monkeypatch, {"user_info": {"auth": 1, "status": status}})


@pytest.mark.parametrize("auth", [0, "0", "", None, "false"])
def test_xtream_auth_rejects_unauthenticated_user_even_when_active(monkeypatch, auth):
    with pytest.raises(ValidationError, match="authentication failed"):
        _validate_with_payload(monkeypatch, {"user_info": {"auth": auth, "status": "Active"}})


@pytest.mark.parametrize("auth", ["1", 1, "true", True, "TRUE"])
def test_xtream_auth_accepts_active_authenticated_user(monkeypatch, auth):
    payload = {"user_info": {"auth": auth, "status": "Active"}}

    assert _validate_with_payload(monkeypatch, payload) == payload


@pytest.mark.parametrize("payload", [[], "ok", None, 5])
def test_xtream_auth_rejects_non_object_payload(monkeypatch, payload):
    with pytest.raises(ParsingError, match="invalid"):
        _validate_with_payload(monkeypatch, payload)


@pytest.mark.parametrize("payload", [{}, {"server_info": {}}, {"user_info": "alice"}, {"user_info": None}])
def test_xtream_auth_rejects_payload_without_user_info(monkeypatch, payload):
    with pytest.raises(ParsingError, match="incomplete"):
        _validate_with_payload(monkeypatch, payload)
