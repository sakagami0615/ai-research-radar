from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any


def _term_matches(term: str, text: str) -> bool:
    term = term.strip()
    if not term:
        return False
    # ASCII keywords need ASCII-aware boundaries.  Unicode text is allowed to
    # match normally, since ASCII word boundaries are not meaningful there.
    if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", term):
        # Allow a trailing plural "s" (e.g. "agents", "LLMs") without
        # reopening the substring-match bug the boundary was added to fix.
        return re.search(rf"(?<![A-Za-z0-9]){re.escape(term)}s?(?![A-Za-z0-9])", text, re.IGNORECASE) is not None
    return term.casefold() in text.casefold()


def classify_relevance(title: str, summary: str, keywords: list[str]) -> dict[str, Any]:
    title_text = str(title or "")
    summary_text = str(summary or "")
    text = f"{title_text} {summary_text}".strip()
    matched_terms = [term for term in keywords if _term_matches(str(term), text)]
    strong_terms = {"rag", "llm", "mcp", "machine learning", "deep learning", "artificial intelligence", "generative ai", "generative-ai"}
    strong_matches = [term for term in matched_terms if str(term).casefold() in strong_terms]
    if strong_matches:
        status = "related"
        reason = "強いAI関連語がタイトルまたは概要で境界付き一致した"
    elif matched_terms:
        status = "uncertain"
        reason = "一般的または曖昧な関連語のみで、内容確認が必要"
    else:
        status = "uncertain"
        reason = "一致する関連語がない、または概要が不足しているため自動で無関係とは判定しない"
    return {
        "status": status,
        "matched_terms": [str(term) for term in matched_terms],
        "reason": reason,
        "method": "keyword",
    }


def restore_abstract(value: object) -> tuple[str, list[str]]:
    if not isinstance(value, Mapping):
        return (str(value or ""), ["abstract_inverted_index_missing_or_not_object"])
    words: dict[int, str] = {}
    diagnostics: list[str] = []
    for word, positions in value.items():
        if not isinstance(word, str) or not isinstance(positions, list):
            diagnostics.append("invalid_abstract_entry")
            continue
        for position in positions:
            if isinstance(position, bool) or not isinstance(position, int) or position < 0:
                diagnostics.append("invalid_abstract_position")
                continue
            if position in words:
                diagnostics.append("conflicting_abstract_position")
                continue
            words[position] = word
    return " ".join(words[position] for position in sorted(words)), diagnostics
