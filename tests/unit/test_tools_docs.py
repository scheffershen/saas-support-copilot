from pathlib import Path

import pytest

from saas_copilot.tools.base import ToolError
from saas_copilot.tools.docs import search_docs

DOCS_ROOT = Path("sample_app/loopline/docs")


def test_search_docs_finds_the_notifications_article() -> None:
    results = search_docs("notification settings", limit=10, root=DOCS_ROOT)
    assert any(doc.path == "docs/notifications.md" for doc in results)


def test_search_docs_result_has_a_citation_ready_path() -> None:
    results = search_docs("ticket", limit=10, root=DOCS_ROOT)
    assert results
    assert all(doc.citation.startswith("docs/") for doc in results)


def test_search_docs_respects_limit() -> None:
    results = search_docs("ticket", limit=1, root=DOCS_ROOT)
    assert len(results) == 1


def test_search_docs_raises_when_nothing_matches() -> None:
    with pytest.raises(ToolError, match="no documentation matched"):
        search_docs("xyzzy-not-a-real-term", limit=10, root=DOCS_ROOT)
