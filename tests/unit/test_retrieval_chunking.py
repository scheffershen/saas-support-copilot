import pytest

from saas_copilot.retrieval.chunking import chunk_text


def test_chunk_text_returns_empty_list_for_empty_input() -> None:
    assert chunk_text("") == []


def test_chunk_text_returns_one_chunk_when_text_fits() -> None:
    assert chunk_text("short text", chunk_size=300, overlap=50) == ["short text"]


def test_chunk_text_splits_long_text_into_multiple_chunks() -> None:
    text = "x" * 700
    chunks = chunk_text(text, chunk_size=300, overlap=50)
    assert len(chunks) > 1
    assert "".join(chunks) != text  # overlap means the joined chunks are longer than the source
    assert all(len(c) <= 300 for c in chunks)


def test_chunk_text_consecutive_chunks_overlap() -> None:
    text = "0123456789" * 40  # 400 chars
    chunks = chunk_text(text, chunk_size=300, overlap=50)
    assert chunks[0][-50:] == chunks[1][:50]


def test_chunk_text_covers_the_whole_input_with_no_gaps() -> None:
    text = "abcdefghij" * 50  # 500 chars, deterministic content
    chunks = chunk_text(text, chunk_size=300, overlap=50)
    # every character index in the original text appears in at least one chunk
    covered = set()
    start = 0
    for chunk in chunks:
        covered.update(range(start, start + len(chunk)))
        start += len(chunk) - 50
    assert covered == set(range(len(text)))


def test_chunk_text_rejects_overlap_not_smaller_than_chunk_size() -> None:
    with pytest.raises(ValueError, match="overlap must be smaller"):
        chunk_text("some text", chunk_size=100, overlap=100)
