import hashlib


def canonical_identity_key(
    market_hash_name: str,
    paint_index: int | None,
    variant: str | None,
) -> str:
    raw = f"{market_hash_name.strip()}|{paint_index or ''}|{(variant or '').strip().lower()}"
    return hashlib.sha256(raw.encode()).hexdigest()
