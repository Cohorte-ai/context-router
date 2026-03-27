"""Token budget management — estimation, scoring, ranking, and trimming."""

from __future__ import annotations

import math

from theaios.context_router.types import ContextChunk

# ---------------------------------------------------------------------------
# Stopwords for relevance scoring (common English words to ignore)
# ---------------------------------------------------------------------------

_STOPWORDS: frozenset[str] = frozenset(
    {
        "a",
        "an",
        "the",
        "and",
        "or",
        "but",
        "in",
        "on",
        "at",
        "to",
        "for",
        "of",
        "with",
        "by",
        "from",
        "is",
        "it",
        "that",
        "this",
        "was",
        "are",
        "be",
        "have",
        "has",
        "had",
        "do",
        "does",
        "did",
        "will",
        "would",
        "could",
        "should",
        "may",
        "might",
        "can",
        "not",
        "no",
        "so",
        "if",
        "then",
        "than",
        "too",
        "very",
        "just",
        "about",
        "up",
        "out",
        "all",
        "its",
        "my",
        "your",
        "our",
        "their",
        "we",
        "they",
        "he",
        "she",
        "i",
        "me",
        "him",
        "her",
        "us",
        "them",
        "what",
        "which",
        "who",
        "when",
        "where",
        "how",
        "as",
        "into",
        "through",
        "during",
        "before",
        "after",
        "above",
        "below",
        "between",
        "each",
        "every",
        "both",
        "few",
        "more",
        "most",
        "other",
        "some",
        "such",
        "only",
        "own",
        "same",
        "also",
        "any",
        "been",
        "being",
        "here",
        "there",
    }
)


# ---------------------------------------------------------------------------
# Token estimation
# ---------------------------------------------------------------------------


def estimate_tokens(text: str, method: str = "chars_div4") -> int:
    """Estimate the number of tokens in a text string.

    Parameters
    ----------
    text : str
        The text to estimate.
    method : str
        Estimation method: "chars_div4" (default), "words", or "whitespace".

    Returns
    -------
    int
        Estimated token count (always >= 1 for non-empty text).
    """
    if not text:
        return 0

    if method == "words":
        # Split on whitespace + punctuation boundaries
        words = text.split()
        return max(1, len(words))

    if method == "whitespace":
        # Simple whitespace splitting — slightly coarser than words
        return max(1, len(text.split()))

    # Default: chars_div4 — roughly 4 chars per token (GPT-like)
    return max(1, math.ceil(len(text) / 4))


# ---------------------------------------------------------------------------
# Relevance scoring
# ---------------------------------------------------------------------------


def score_relevance(query_text: str, chunk: ContextChunk) -> float:
    """Score the relevance of a chunk to a query using keyword overlap.

    Uses a simple Jaccard-like similarity between non-stopword tokens
    in the query and the chunk content. Returns a float in [0.0, 1.0].

    Parameters
    ----------
    query_text : str
        The query text to compare against.
    chunk : ContextChunk
        The chunk to score.

    Returns
    -------
    float
        Relevance score between 0.0 and 1.0.
    """
    query_tokens = _extract_keywords(query_text)
    if not query_tokens:
        return 0.0

    chunk_tokens = _extract_keywords(chunk.content)
    if not chunk_tokens:
        return 0.0

    # Also include title keywords with a boost
    title_tokens = _extract_keywords(chunk.title)
    chunk_tokens = chunk_tokens | title_tokens

    overlap = query_tokens & chunk_tokens
    if not overlap:
        return 0.0

    # Jaccard similarity weighted toward query coverage
    query_coverage = len(overlap) / len(query_tokens)
    return min(1.0, query_coverage)


def _extract_keywords(text: str) -> set[str]:
    """Extract non-stopword lowercase tokens from text."""
    tokens = set()
    for word in text.lower().split():
        # Strip common punctuation
        cleaned = word.strip(".,;:!?\"'()[]{}/-")
        if cleaned and cleaned not in _STOPWORDS and len(cleaned) > 1:
            tokens.add(cleaned)
    return tokens


# ---------------------------------------------------------------------------
# Ranking
# ---------------------------------------------------------------------------


def rank_chunks(chunks: list[ContextChunk], ranking: str) -> list[ContextChunk]:
    """Sort chunks according to the specified ranking strategy.

    Parameters
    ----------
    chunks : list[ContextChunk]
        Chunks to sort.
    ranking : str
        Ranking strategy: "relevance", "recency", or "manual".

    Returns
    -------
    list[ContextChunk]
        Sorted chunks (highest priority first).
    """
    if ranking == "relevance":
        return sorted(chunks, key=lambda c: c.relevance_score, reverse=True)

    if ranking == "recency":

        def _mtime_key(c: ContextChunk) -> float:
            val = c.metadata.get("mtime", 0)
            return float(val) if isinstance(val, (int, float)) else 0.0

        return sorted(chunks, key=_mtime_key, reverse=True)

    # "manual" — preserve insertion order
    return list(chunks)


# ---------------------------------------------------------------------------
# Budget application
# ---------------------------------------------------------------------------


def apply_budget(
    chunks: list[ContextChunk],
    max_tokens: int,
    *,
    truncation: str = "drop",
    reserve_tokens: int = 0,
    estimator: str = "chars_div4",
) -> tuple[list[ContextChunk], bool]:
    """Apply a token budget to a list of chunks.

    Processes chunks in order (already ranked). Keeps adding chunks
    until the budget is exhausted. Depending on the truncation strategy,
    the last chunk may be truncated or dropped.

    Parameters
    ----------
    chunks : list[ContextChunk]
        Pre-ranked chunks to fit within budget.
    max_tokens : int
        Maximum total token budget.
    truncation : str
        What to do when a chunk exceeds remaining budget:
        "drop" — skip it, "truncate_end" — cut from the end,
        "truncate_middle" — cut from the middle.
    reserve_tokens : int
        Tokens to reserve (subtracted from max_tokens).
    estimator : str
        Token estimation method.

    Returns
    -------
    tuple[list[ContextChunk], bool]
        A tuple of (kept_chunks, was_truncated).
    """
    available = max_tokens - reserve_tokens
    if available <= 0:
        return [], bool(chunks)

    kept: list[ContextChunk] = []
    used = 0
    was_truncated = False

    for chunk in chunks:
        tokens = chunk.token_count or estimate_tokens(chunk.content, estimator)
        remaining = available - used

        if remaining <= 0:
            was_truncated = True
            break

        if tokens <= remaining:
            kept.append(chunk)
            used += tokens
        elif truncation == "truncate_end":
            truncated_content = _truncate_end(chunk.content, remaining, estimator)
            truncated_chunk = ContextChunk(
                content=truncated_content,
                source=chunk.source,
                title=chunk.title,
                path=chunk.path,
                relevance_score=chunk.relevance_score,
                token_count=estimate_tokens(truncated_content, estimator),
                metadata=dict(chunk.metadata),
            )
            kept.append(truncated_chunk)
            used += truncated_chunk.token_count
            was_truncated = True
        elif truncation == "truncate_middle":
            truncated_content = _truncate_middle(chunk.content, remaining, estimator)
            truncated_chunk = ContextChunk(
                content=truncated_content,
                source=chunk.source,
                title=chunk.title,
                path=chunk.path,
                relevance_score=chunk.relevance_score,
                token_count=estimate_tokens(truncated_content, estimator),
                metadata=dict(chunk.metadata),
            )
            kept.append(truncated_chunk)
            used += truncated_chunk.token_count
            was_truncated = True
        else:
            # "drop" — skip this chunk
            was_truncated = True

    # If there were more chunks we didn't process
    if len(kept) < len(chunks):
        was_truncated = True

    return kept, was_truncated


def _truncate_end(text: str, max_tokens: int, estimator: str) -> str:
    """Truncate text from the end to fit within max_tokens."""
    if estimator == "words" or estimator == "whitespace":
        words = text.split()
        # Binary search for the right number of words
        lo, hi = 0, len(words)
        while lo < hi:
            mid = (lo + hi + 1) // 2
            candidate = " ".join(words[:mid])
            if estimate_tokens(candidate, estimator) <= max_tokens:
                lo = mid
            else:
                hi = mid - 1
        return " ".join(words[:lo]) + " [...]" if lo < len(words) else text

    # chars_div4: approximate character count
    max_chars = max_tokens * 4
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + " [...]"


def _truncate_middle(text: str, max_tokens: int, estimator: str) -> str:
    """Truncate text from the middle to fit within max_tokens."""
    if estimator == "words" or estimator == "whitespace":
        words = text.split()
        target_words = 0
        for i in range(len(words)):
            candidate = " ".join(words[: i + 1])
            if estimate_tokens(candidate, estimator) > max_tokens:
                break
            target_words = i + 1
        if target_words >= len(words):
            return text
        half = target_words // 2
        head = " ".join(words[:half])
        tail = " ".join(words[-(target_words - half) :])
        return head + "\n[...truncated...]\n" + tail

    # chars_div4
    max_chars = max_tokens * 4
    if len(text) <= max_chars:
        return text
    half = max_chars // 2
    return text[:half] + "\n[...truncated...]\n" + text[-half:]
