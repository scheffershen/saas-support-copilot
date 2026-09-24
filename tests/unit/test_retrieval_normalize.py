from saas_copilot.retrieval.normalize import normalize_text


def test_normalize_strips_markdown_headings() -> None:
    assert normalize_text("# Getting started\n\nSome text.") == "Getting started\n\nSome text."


def test_normalize_converts_crlf_to_lf() -> None:
    assert "\r" not in normalize_text("line one\r\nline two\r\n")


def test_normalize_collapses_three_or_more_blank_lines() -> None:
    result = normalize_text("a\n\n\n\n\nb")
    assert result == "a\n\nb"


def test_normalize_trims_leading_and_trailing_whitespace() -> None:
    assert normalize_text("  \n  hello  \n  ") == "hello"


def test_normalize_leaves_a_single_blank_line_alone() -> None:
    assert normalize_text("a\n\nb") == "a\n\nb"
