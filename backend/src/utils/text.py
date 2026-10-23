"""Small text helpers."""


def sanitize_pasted_text(raw: str) -> str:
    """Normalize free-form text for safe use: one kind of line break, no control characters."""
    cleaned = raw.replace("\r\n", "\n").replace("\r", "\n")
    cleaned = "".join(
        ch for ch in cleaned
        if ch in ("\t", "\n") or (ord(ch) >= 32 and ord(ch) != 127)
    )
    return cleaned.strip()
