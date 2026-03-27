"""Tests for token budget management — estimation, scoring, ranking, trimming."""

from __future__ import annotations


from theaios.context_router.budget import (
    apply_budget,
    estimate_tokens,
    rank_chunks,
    score_relevance,
)
from theaios.context_router.types import ContextChunk


class TestEstimateTokens:
    """Tests for estimate_tokens()."""

    def test_chars_div4_method(self) -> None:
        text = "Hello world"  # 11 chars -> ceil(11/4) = 3
        result = estimate_tokens(text, "chars_div4")
        assert result == 3

    def test_chars_div4_is_default(self) -> None:
        text = "Hello world"
        assert estimate_tokens(text) == estimate_tokens(text, "chars_div4")

    def test_chars_div4_empty(self) -> None:
        assert estimate_tokens("", "chars_div4") == 0

    def test_chars_div4_minimum_one(self) -> None:
        assert estimate_tokens("a", "chars_div4") == 1

    def test_whitespace_method(self) -> None:
        text = "one two three four"  # 4 words
        result = estimate_tokens(text, "whitespace")
        assert result == 4

    def test_whitespace_empty(self) -> None:
        assert estimate_tokens("", "whitespace") == 0

    def test_whitespace_single_word(self) -> None:
        assert estimate_tokens("hello", "whitespace") == 1

    def test_words_method(self) -> None:
        text = "one two three four five"  # 5 words
        result = estimate_tokens(text, "words")
        assert result == 5

    def test_words_empty(self) -> None:
        assert estimate_tokens("", "words") == 0


class TestScoreRelevance:
    """Tests for score_relevance() keyword overlap scoring."""

    def test_perfect_overlap(self) -> None:
        chunk = ContextChunk(
            content="remote work policy guidelines",
            source="docs",
            title="Remote Work",
        )
        score = score_relevance("remote work policy", chunk)
        assert score > 0.5

    def test_no_overlap(self) -> None:
        chunk = ContextChunk(
            content="database migration strategy",
            source="docs",
        )
        score = score_relevance("remote work policy", chunk)
        assert score == 0.0

    def test_partial_overlap(self) -> None:
        chunk = ContextChunk(
            content="company travel policy for international trips",
            source="docs",
        )
        score = score_relevance("travel policy expenses", chunk)
        assert 0.0 < score < 1.0

    def test_stopwords_ignored(self) -> None:
        chunk = ContextChunk(content="the and or but", source="docs")
        score = score_relevance("the and or", chunk)
        assert score == 0.0

    def test_empty_query(self) -> None:
        chunk = ContextChunk(content="some content here", source="docs")
        score = score_relevance("", chunk)
        assert score == 0.0

    def test_empty_chunk(self) -> None:
        chunk = ContextChunk(content="", source="docs")
        score = score_relevance("remote work", chunk)
        assert score == 0.0

    def test_title_boosts_relevance(self) -> None:
        chunk_with_title = ContextChunk(
            content="guidelines and procedures",
            source="docs",
            title="Remote Work Policy",
        )
        chunk_no_title = ContextChunk(
            content="guidelines and procedures",
            source="docs",
        )
        score_with = score_relevance("remote work policy", chunk_with_title)
        score_without = score_relevance("remote work policy", chunk_no_title)
        assert score_with > score_without

    def test_score_capped_at_one(self) -> None:
        chunk = ContextChunk(
            content="remote work policy guidelines overview",
            source="docs",
            title="Remote Work Policy",
        )
        score = score_relevance("remote work policy", chunk)
        assert score <= 1.0


class TestRankChunks:
    """Tests for rank_chunks()."""

    def test_rank_by_relevance(self) -> None:
        chunks = [
            ContextChunk(content="low", source="a", relevance_score=0.1),
            ContextChunk(content="high", source="b", relevance_score=0.9),
            ContextChunk(content="mid", source="c", relevance_score=0.5),
        ]
        ranked = rank_chunks(chunks, "relevance")
        scores = [c.relevance_score for c in ranked]
        assert scores == [0.9, 0.5, 0.1]

    def test_rank_by_priority_manual(self) -> None:
        chunks = [
            ContextChunk(content="first", source="a"),
            ContextChunk(content="second", source="b"),
            ContextChunk(content="third", source="c"),
        ]
        ranked = rank_chunks(chunks, "manual")
        # Manual preserves insertion order
        contents = [c.content for c in ranked]
        assert contents == ["first", "second", "third"]

    def test_rank_by_recency(self) -> None:
        chunks = [
            ContextChunk(content="old", source="a", metadata={"mtime": 1000.0}),
            ContextChunk(content="new", source="b", metadata={"mtime": 3000.0}),
            ContextChunk(content="mid", source="c", metadata={"mtime": 2000.0}),
        ]
        ranked = rank_chunks(chunks, "recency")
        contents = [c.content for c in ranked]
        assert contents == ["new", "mid", "old"]

    def test_rank_by_recency_missing_mtime(self) -> None:
        chunks = [
            ContextChunk(content="has_mtime", source="a", metadata={"mtime": 2000.0}),
            ContextChunk(content="no_mtime", source="b", metadata={}),
        ]
        ranked = rank_chunks(chunks, "recency")
        # Chunk with mtime should come first (higher mtime)
        assert ranked[0].content == "has_mtime"


class TestApplyBudget:
    """Tests for apply_budget()."""

    def test_all_chunks_fit(self) -> None:
        chunks = [
            ContextChunk(content="hello", source="a", token_count=10),
            ContextChunk(content="world", source="b", token_count=10),
        ]
        kept, was_truncated = apply_budget(chunks, max_tokens=100)
        assert len(kept) == 2
        assert was_truncated is False

    def test_drop_truncation(self) -> None:
        chunks = [
            ContextChunk(content="first", source="a", token_count=50),
            ContextChunk(content="second", source="b", token_count=50),
            ContextChunk(content="third", source="c", token_count=50),
        ]
        kept, was_truncated = apply_budget(chunks, max_tokens=100, truncation="drop")
        assert len(kept) == 2
        assert was_truncated is True

    def test_global_limit_enforced(self) -> None:
        chunks = [
            ContextChunk(content="x" * 400, source="a", token_count=100),
            ContextChunk(content="y" * 400, source="b", token_count=100),
        ]
        kept, was_truncated = apply_budget(chunks, max_tokens=50, truncation="drop")
        assert len(kept) == 0
        assert was_truncated is True

    def test_reserve_tokens(self) -> None:
        chunks = [
            ContextChunk(content="data", source="a", token_count=50),
        ]
        kept, was_truncated = apply_budget(
            chunks, max_tokens=100, reserve_tokens=60, truncation="drop"
        )
        # Available = 100 - 60 = 40, chunk needs 50 -> dropped
        assert len(kept) == 0
        assert was_truncated is True

    def test_truncate_end(self) -> None:
        long_content = "word " * 100  # 100 words
        chunks = [
            ContextChunk(content=long_content, source="a", token_count=100),
        ]
        kept, was_truncated = apply_budget(chunks, max_tokens=20, truncation="truncate_end")
        assert len(kept) == 1
        assert was_truncated is True
        assert len(kept[0].content) < len(long_content)
        # Token count is approximate due to the "[...]" truncation marker
        assert kept[0].token_count < 100

    def test_truncate_middle(self) -> None:
        long_content = "word " * 100
        chunks = [
            ContextChunk(content=long_content, source="a", token_count=100),
        ]
        kept, was_truncated = apply_budget(chunks, max_tokens=20, truncation="truncate_middle")
        assert len(kept) == 1
        assert was_truncated is True
        assert "[...truncated...]" in kept[0].content

    def test_empty_chunks_no_truncation(self) -> None:
        kept, was_truncated = apply_budget([], max_tokens=100)
        assert kept == []
        assert was_truncated is False

    def test_zero_budget(self) -> None:
        chunks = [
            ContextChunk(content="data", source="a", token_count=10),
        ]
        kept, was_truncated = apply_budget(chunks, max_tokens=0, reserve_tokens=0)
        assert kept == []
        assert was_truncated is True

    def test_per_chunk_token_count_used(self) -> None:
        chunks = [
            ContextChunk(content="short", source="a", token_count=5),
            ContextChunk(content="medium content here", source="b", token_count=15),
            ContextChunk(content="long content string value", source="c", token_count=25),
        ]
        kept, was_truncated = apply_budget(chunks, max_tokens=20, truncation="drop")
        # First two fit (5+15=20), third dropped
        assert len(kept) == 2
        assert was_truncated is True
