"""URL predicates shared by anything that hands a link to the outside world."""
from __future__ import annotations

from urllib.parse import urlparse

LOCAL_HOSTS = {"localhost", "0.0.0.0", "::1"}


def is_public_http_url(url: str) -> bool:
    """True when a phone or a mail client could actually open this url.

    Telegram refuses inline URL buttons it cannot resolve ("Wrong HTTP URL"),
    and a verification link on localhost is dead the moment it leaves this
    machine — both failures look like "the feature is broken" from outside.
    """
    parsed = urlparse(url)
    host = parsed.hostname or ""
    return (
        parsed.scheme in ("http", "https")
        and "." in host
        and host not in LOCAL_HOSTS
        and not host.startswith("127.")
    )
