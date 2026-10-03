from ai_research_radar.normalization.relevance import classify_relevance, restore_abstract


def test_short_terms_require_ascii_boundaries():
    assert classify_relevance("brokerage", "fragment chair", ["rag", "agent"])['matched_terms'] == []
    assert classify_relevance("RAG-based", "LLM活用", ["rag", "llm"])['status'] == "related"


def test_plural_forms_still_match():
    result = classify_relevance("New AI agents were released today", "with several LLMs improving performance", ["llm", "rag", "agent", "mcp"])
    assert set(result["matched_terms"]) == {"llm", "agent"}


def test_agent_only_is_uncertain():
    result = classify_relevance("An agent utility", "", ["agent"])
    assert result["status"] == "uncertain"
    assert result["method"] == "keyword"


def test_missing_summary_is_not_unrelated():
    result = classify_relevance("A tool", "", ["rag"])
    assert result["status"] == "uncertain"
    assert result["reason"]


def test_repeated_words_restored():
    text, diagnostics = restore_abstract({"a": [0, 2], "test": [1]})
    assert text == "a test a"
    assert diagnostics == []


def test_invalid_abstract_positions_are_reported():
    text, diagnostics = restore_abstract({"a": [-1, 0, "x"], "b": [0]})
    assert text
    assert diagnostics
