from __future__ import annotations

import xxhash


def build_content_text(title: str, meta_description: str, headings: list[str], body_text: str) -> str:
    chunks = [title.strip(), meta_description.strip(), "\n".join(headings).strip(), body_text.strip()]
    return "\n\n".join(chunk for chunk in chunks if chunk)


def fingerprint_text(text: str) -> str:
    return f"xxh3:{xxhash.xxh3_64_hexdigest(text.encode('utf-8'))}"


def truncate_utf8(text: str, *, max_bytes: int) -> str:
    encoded = text.encode("utf-8")
    if len(encoded) <= max_bytes:
        return text

    truncated = encoded[:max_bytes]
    while truncated:
        try:
            trimmed = truncated.decode("utf-8")
            return trimmed.rstrip()
        except UnicodeDecodeError:
            truncated = truncated[:-1]
    return ""
