from __future__ import annotations

import logging
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import requests
from requests import Response
from requests.exceptions import ConnectionError, HTTPError, RequestException, SSLError, Timeout

from core.errors import NetworkError, ParsingError, ValidationError
from core.models import Channel, XtreamCredentials


logger = logging.getLogger(__name__)


class XtreamClient:
    """Minimal Xtream-compatible client for live TV authentication and channel loading."""

    def __init__(self, timeout: int = 20):
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "SimpleIPTVPlayer/1.0",
                "Accept": "application/json, text/plain, */*",
                "Connection": "close",
            }
        )
        self._last_effective_credentials: XtreamCredentials | None = None

    @property
    def last_effective_credentials(self) -> XtreamCredentials | None:
        return self._last_effective_credentials

    def validate_credentials(self, credentials: XtreamCredentials) -> dict[str, Any]:
        logger.info(
            "Validating Xtream credentials for %s (timeout=%ss)",
            credentials.normalized().redacted_summary(),
            self.timeout,
        )
        payload = self._request_json(credentials, {})
        self._ensure_authenticated(payload)
        logger.info(
            "Xtream authentication succeeded for %s",
            credentials.normalized().redacted_summary(),
        )
        return payload

    def fetch_live_categories(self, credentials: XtreamCredentials) -> dict[str, str]:
        logger.debug(
            "Fetching Xtream live categories for %s",
            credentials.normalized().redacted_summary(),
        )
        payload = self._request_json(credentials, {"action": "get_live_categories"})
        if not isinstance(payload, list):
            logger.warning(
                "Xtream categories payload had unexpected type for %s: %s",
                credentials.normalized().redacted_summary(),
                type(payload).__name__,
            )
            raise ParsingError("Xtream categories response was invalid")
        categories: dict[str, str] = {}
        for item in payload:
            if not isinstance(item, dict):
                continue
            category_id = str(item.get("category_id", "")).strip()
            category_name = str(item.get("category_name", "")).strip()
            if category_id and category_name:
                categories[category_id] = category_name
        logger.debug(
            "Fetched %s Xtream live categories for %s",
            len(categories),
            credentials.normalized().redacted_summary(),
        )
        return categories

    def fetch_live_channels(self, credentials: XtreamCredentials) -> list[Channel]:
        logger.info(
            "Fetching Xtream live channels for %s",
            credentials.normalized().redacted_summary(),
        )
        categories = self.fetch_live_categories(credentials)
        payload = self._request_json(credentials, {"action": "get_live_streams"})
        if not isinstance(payload, list):
            logger.warning(
                "Xtream live streams payload had unexpected type for %s: %s",
                credentials.normalized().redacted_summary(),
                type(payload).__name__,
            )
            raise ParsingError("Xtream live streams response was invalid")

        channels: list[Channel] = []
        skipped_non_live = 0
        skipped_invalid = 0
        for item in payload:
            if not isinstance(item, dict):
                skipped_invalid += 1
                continue
            if str(item.get("stream_type", "live")).strip().lower() not in {"", "live"}:
                skipped_non_live += 1
                continue

            stream_id = str(item.get("stream_id", "")).strip()
            name = str(item.get("name", "")).strip()
            if not stream_id or not name:
                skipped_invalid += 1
                continue

            category_id = str(item.get("category_id", "")).strip()
            group_name = categories.get(category_id) or str(item.get("category_name", "")).strip()
            channel_number = self._to_int(item.get("num"))

            channels.append(
                Channel(
                    name=name,
                    url=self._build_live_stream_url(self.last_effective_credentials or credentials, stream_id),
                    group=group_name,
                    logo=str(item.get("stream_icon", "") or "").strip(),
                    epg_id=str(
                        item.get("epg_channel_id")
                        or item.get("epg_channel")
                        or item.get("channel_id")
                        or ""
                    ).strip(),
                    channel_number=channel_number,
                )
            )

        logger.debug(
            "Xtream live stream mapping for %s: %s channels, %s non-live skipped, %s invalid skipped",
            credentials.normalized().redacted_summary(),
            len(channels),
            skipped_non_live,
            skipped_invalid,
        )
        if not channels:
            logger.warning(
                "Xtream source returned no usable live channels for %s",
                credentials.normalized().redacted_summary(),
            )
            raise ValidationError("Xtream source did not return any live channels")
        return channels

    def _request_json(
        self,
        credentials: XtreamCredentials,
        params: dict[str, str],
    ) -> Any:
        normalized = credentials.normalized()
        self._last_effective_credentials = normalized
        payload, effective_credentials = self._request_json_with_fallback(normalized, params)
        self._last_effective_credentials = effective_credentials
        return payload

    def _request_json_with_fallback(
        self,
        credentials: XtreamCredentials,
        params: dict[str, str],
    ) -> tuple[Any, XtreamCredentials]:
        url = self._build_api_url(credentials, params)
        action = params.get("action", "authenticate")
        logger.debug(
            "Issuing Xtream %s request to %s",
            action,
            self._sanitize_request_url(url),
        )
        try:
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
            logger.debug(
                "Xtream %s response received from %s with status=%s content_type=%s",
                action,
                credentials.redacted_summary(),
                getattr(response, "status_code", "unknown"),
                getattr(getattr(response, "headers", {}), "get", lambda *_args, **_kwargs: "")(
                    "Content-Type", ""
                ),
            )
            return (
                self._parse_json(response, source=credentials.redacted_summary(), action=action),
                credentials,
            )
        except Timeout as exc:
            logger.warning(
                "Xtream %s request timed out for %s",
                action,
                credentials.redacted_summary(),
            )
            raise NetworkError("Xtream request timed out") from exc
        except HTTPError as exc:
            logger.warning(
                "Xtream %s request returned HTTP error for %s: %s",
                action,
                credentials.redacted_summary(),
                exc,
            )
            raise NetworkError("Failed to contact Xtream source") from exc
        except (ConnectionError, SSLError) as exc:
            if self._should_try_https_fallback(credentials):
                fallback_credentials = XtreamCredentials(
                    server_url=self._force_https(credentials.server_url),
                    username=credentials.username,
                    password=credentials.password,
                    output=credentials.output,
                ).normalized()
                logger.info(
                    "Retrying Xtream %s request over HTTPS for %s",
                    action,
                    credentials.redacted_summary(),
                )
                try:
                    payload, effective = self._request_json_with_fallback(
                        fallback_credentials,
                        params,
                    )
                    logger.info(
                        "Xtream source required HTTPS; upgraded %s to %s",
                        credentials.redacted_summary(),
                        effective.redacted_summary(),
                    )
                    return payload, effective
                except NetworkError:
                    logger.warning(
                        "Xtream HTTPS retry also failed for %s",
                        fallback_credentials.redacted_summary(),
                    )
                    raise NetworkError(
                        "Failed to contact Xtream source over HTTP or HTTPS"
                    ) from exc
            logger.warning(
                "Xtream %s request failed for %s: %s",
                action,
                credentials.redacted_summary(),
                exc,
            )
            raise NetworkError("Failed to contact Xtream source") from exc
        except RequestException as exc:
            logger.warning(
                "Xtream %s request failed for %s: %s",
                action,
                credentials.redacted_summary(),
                exc,
            )
            raise NetworkError("Failed to contact Xtream source") from exc

    @staticmethod
    def _build_api_url(credentials: XtreamCredentials, params: dict[str, str]) -> str:
        query = {
            "username": credentials.username,
            "password": credentials.password,
        }
        query.update(params)
        return f"{credentials.server_url}/player_api.php?{urlencode(query)}"

    @staticmethod
    def _parse_json(response: Response, *, source: str, action: str) -> Any:
        try:
            payload = response.json()
            if isinstance(payload, list):
                size_hint = len(payload)
            elif isinstance(payload, dict):
                size_hint = len(payload.keys())
            else:
                size_hint = 0
            logger.debug(
                "Parsed Xtream %s payload for %s: type=%s size_hint=%s",
                action,
                source,
                type(payload).__name__,
                size_hint,
            )
            return payload
        except ValueError as exc:
            logger.warning(
                "Xtream %s response contained invalid JSON for %s",
                action,
                source,
            )
            raise ParsingError("Xtream source returned invalid JSON") from exc

    @staticmethod
    def _ensure_authenticated(payload: Any) -> None:
        if not isinstance(payload, dict):
            raise ParsingError("Xtream authentication response was invalid")
        user_info = payload.get("user_info")
        if not isinstance(user_info, dict):
            raise ParsingError("Xtream authentication response was incomplete")
        auth_value = str(user_info.get("auth", "")).strip().lower()
        status_value = str(user_info.get("status", "")).strip().lower()
        logger.debug(
            "Xtream auth payload summary: auth=%s status=%s has_user_info=%s",
            auth_value,
            status_value,
            True,
        )
        if auth_value not in {"1", "true"} or status_value in {"disabled", "banned"}:
            raise ValidationError("Xtream authentication failed. Check the server URL, username, and password.")

    @staticmethod
    def _build_live_stream_url(credentials: XtreamCredentials, stream_id: str) -> str:
        normalized = credentials.normalized()
        return (
            f"{normalized.server_url}/live/"
            f"{normalized.username}/{normalized.password}/{stream_id}.{normalized.output}"
        )

    @staticmethod
    def _to_int(value: Any) -> int:
        try:
            return int(str(value).strip())
        except (TypeError, ValueError):
            return 0

    @staticmethod
    def _sanitize_request_url(url: str) -> str:
        parsed = urlparse(url)
        query = []
        for key, value in parse_qsl(parsed.query, keep_blank_values=True):
            if key.lower() == "password":
                query.append((key, "***"))
            else:
                query.append((key, value))
        return urlunparse(parsed._replace(query=urlencode(query)))

    @staticmethod
    def _should_try_https_fallback(credentials: XtreamCredentials) -> bool:
        parsed = urlparse(credentials.server_url)
        return parsed.scheme.lower() == "http"

    @staticmethod
    def _force_https(url: str) -> str:
        parsed = urlparse(url)
        return urlunparse(parsed._replace(scheme="https"))
