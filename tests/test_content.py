from app.utils.content import build_content_text, truncate_utf8


def test_build_content_text_preserves_priority_sections() -> None:
    content = build_content_text(
        "Title",
        "Meta description",
        ["Heading 1", "Heading 2"],
        "Body paragraph",
    )
    assert content == "Title\n\nMeta description\n\nHeading 1\nHeading 2\n\nBody paragraph"


def test_truncate_utf8_caps_encoded_size() -> None:
    text = "a" * 100
    truncated = truncate_utf8(text, max_bytes=12)
    assert truncated == "a" * 12
