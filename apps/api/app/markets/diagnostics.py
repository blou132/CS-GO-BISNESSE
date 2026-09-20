"""Allowlisted metadata only: never retain upstream bodies, cookies or auth headers."""

from collections.abc import Mapping

from .http import retry_after_seconds


def response_metadata(headers: Mapping[str, str]) -> dict[str, object]:
    normalized = {key.lower(): value for key, value in headers.items()}
    result: dict[str, object] = {}
    media_type = normalized.get("content-type", "").split(";", 1)[0].strip().lower()
    result["content_type"] = (
        media_type if media_type in {"application/json", "text/html", "text/plain"} else "OTHER"
    )
    result["retry_after_seconds"] = retry_after_seconds(normalized.get("retry-after"))
    result["cloudflare_challenge"] = normalized.get("cf-mitigated") == "challenge"
    result["server_cloudflare"] = normalized.get("server", "").lower() == "cloudflare"
    for key in (
        "x-ratelimit-limit",
        "x-ratelimit-remaining",
        "x-ratelimit-reset",
        "ratelimit-limit",
        "ratelimit-remaining",
        "ratelimit-reset",
    ):
        value = normalized.get(key, "")
        if value.isascii() and value.isdigit() and len(value) <= 16:
            result[key] = int(value)
    return result
