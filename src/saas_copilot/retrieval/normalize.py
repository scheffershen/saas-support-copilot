"""Light text normalization before chunking. Deliberately NOT lowercasing or
stripping punctuation here - BM25's tokenizer and the embedding client each do their
own normalization for their own purposes; this step is shared prep (fix line endings,
drop layout characters that carry no retrieval-relevant meaning), not final processing.
"""
from __future__ import annotations

import re

_MULTI_BLANK_LINE_RE = re.compile(r"\n{3,}")
_MARKDOWN_HEADING_RE = re.compile(r"^#{1,6}\s+", re.MULTILINE)


def normalize_text(text: str) -> str:
    text = text.replace("\r\n", "\n")
    text = _MARKDOWN_HEADING_RE.sub("", text)
    text = _MULTI_BLANK_LINE_RE.sub("\n\n", text)
    return text.strip()
