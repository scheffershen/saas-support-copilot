import pytest

from saas_copilot.models import Document, SourceFile


def test_document_citation_with_chunk_id() -> None:
    doc = Document(path="docs/notifications.md", title="Notifications", content="...", chunk_id=2)
    assert doc.citation == "docs/notifications.md#chunk-2"


def test_document_citation_without_chunk_id() -> None:
    doc = Document(path="docs/notifications.md", title="Notifications", content="...")
    assert doc.citation == "docs/notifications.md"


def test_document_is_immutable() -> None:
    doc = Document(path="docs/notifications.md", title="Notifications", content="...")
    with pytest.raises(AttributeError):
        doc.title = "Something else"  # type: ignore[misc]


def test_source_file_line_count() -> None:
    source = SourceFile(path="app/notifications.py", language="python", content="a\nb\nc")
    assert source.line_count == 3


def test_source_file_line_happy_path() -> None:
    source = SourceFile(path="app/notifications.py", language="python", content="a\nb\nc")
    assert source.line(2) == "b"


def test_source_file_line_out_of_range_raises_with_clear_message() -> None:
    source = SourceFile(path="app/notifications.py", language="python", content="a\nb\nc")
    with pytest.raises(IndexError, match=r"app/notifications\.py has no line 10 \(file has 3 lines\)"):
        source.line(10)
