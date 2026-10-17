"""Credential redaction helpers shared by services that log or raise source URLs."""

import re
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

_SECRET_KEYS = {"password", "passwd", "pass", "pwd"}
_QUERY_SECRET_RE = re.compile(r"(?i)(password|passwd|pass|pwd)=[^&\s'\"]+")
_USERINFO_SECRET_RE = re.compile(r"(?i)(\b[a-z][a-z0-9+.-]*://[^/\s:@]*:)[^@/\s]+(@)")


def redact_url(url: str) -> str:
    """Mask a userinfo password and password-like query values in a URL.

    Scheme, host, port, path and other parameters are kept for diagnostics.
    Returns the input unchanged when there is nothing to mask or it cannot be parsed.
    """
    try:
        parsed = urlparse(url)
        netloc = parsed.netloc
        if parsed.password is not None:
            host = parsed.hostname or ""
            if parsed.port is not None:
                host = f"{host}:{parsed.port}"
            userinfo = parsed.username or ""
            netloc = f"{userinfo}:***@{host}" if userinfo else f":***@{host}"

        query = parsed.query
        if query:
            query = urlencode(
                [
                    (key, "***" if key.lower() in _SECRET_KEYS else value)
                    for key, value in parse_qsl(query, keep_blank_values=True)
                ]
            )

        if netloc == parsed.netloc and query == parsed.query:
            return url
        return urlunparse(parsed._replace(netloc=netloc, query=query))
    except ValueError:
        # Unparseable (e.g. bad port): fall back to regex masking rather than echoing secrets.
        return redact_text(url)


def redact_identity(identity: str) -> str:
    """Mask the URL part of a ``url::<url>`` source identity; other identities pass through."""
    prefix = "url::"
    if identity.startswith(prefix):
        return prefix + redact_url(identity[len(prefix) :])
    return identity


def redact_text(text: str) -> str:
    """Mask secrets embedded in free text such as ``requests`` exception strings."""
    masked = _QUERY_SECRET_RE.sub(r"\1=***", str(text))
    return _USERINFO_SECRET_RE.sub(r"\1***\2", masked)
