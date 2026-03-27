"""Tests for the disk-based cache with TTL."""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from theaios.context_router.cache import Cache
from theaios.context_router.types import CacheConfig, ContextChunk


class TestCache:
    """Tests for Cache put/get/invalidate/stats."""

    @pytest.fixture()
    def cache_dir(self, tmp_path: Path) -> Path:
        d = tmp_path / "cache"
        d.mkdir()
        return d

    @pytest.fixture()
    def cache(self, cache_dir: Path) -> Cache:
        config = CacheConfig(
            enabled=True,
            directory=str(cache_dir),
            ttl=300,
            max_entries=100,
        )
        return Cache(config)

    @pytest.fixture()
    def sample_chunks(self) -> list[ContextChunk]:
        return [
            ContextChunk(
                content="First chunk content.",
                source="docs",
                title="First",
                path="docs/first.md",
                relevance_score=0.8,
                token_count=5,
                metadata={"mtime": 1000.0},
            ),
            ContextChunk(
                content="Second chunk content.",
                source="docs",
                title="Second",
                path="docs/second.md",
                relevance_score=0.6,
                token_count=5,
            ),
        ]

    def test_put_and_get(self, cache: Cache, sample_chunks: list[ContextChunk]) -> None:
        cache.put("docs", "test query", sample_chunks)
        result = cache.get("docs", "test query")

        assert result is not None
        assert len(result) == 2
        assert result[0].content == "First chunk content."
        assert result[0].source == "docs"
        assert result[0].title == "First"
        assert result[0].path == "docs/first.md"
        assert result[0].relevance_score == 0.8
        assert result[0].token_count == 5
        assert result[1].content == "Second chunk content."

    def test_get_miss_returns_none(self, cache: Cache) -> None:
        result = cache.get("docs", "nonexistent query")
        assert result is None

    def test_ttl_expiry(self, cache_dir: Path, sample_chunks: list[ContextChunk]) -> None:
        config = CacheConfig(
            enabled=True,
            directory=str(cache_dir),
            ttl=1,  # 1 second TTL
            max_entries=100,
        )
        cache = Cache(config)

        cache.put("docs", "query", sample_chunks)

        # Should be available immediately
        result = cache.get("docs", "query")
        assert result is not None

        # Wait for TTL to expire
        time.sleep(1.5)

        # Should be expired now
        result = cache.get("docs", "query")
        assert result is None

    def test_invalidate_by_source(self, cache: Cache, sample_chunks: list[ContextChunk]) -> None:
        cache.put("docs", "query1", sample_chunks)
        cache.put("docs", "query2", sample_chunks)
        cache.put("api", "query1", sample_chunks)

        count = cache.invalidate(source="docs")
        assert count == 2

        # docs entries should be gone
        assert cache.get("docs", "query1") is None
        assert cache.get("docs", "query2") is None
        # api entry should remain
        assert cache.get("api", "query1") is not None

    def test_invalidate_all(self, cache: Cache, sample_chunks: list[ContextChunk]) -> None:
        cache.put("docs", "query1", sample_chunks)
        cache.put("api", "query2", sample_chunks)

        count = cache.invalidate()
        assert count == 2

        assert cache.get("docs", "query1") is None
        assert cache.get("api", "query2") is None

    def test_stats(self, cache: Cache, sample_chunks: list[ContextChunk]) -> None:
        cache.put("docs", "query1", sample_chunks)
        cache.put("docs", "query2", sample_chunks)

        s = cache.stats()
        assert s["enabled"] is True
        assert s["entries"] == 2
        assert s["total_size_bytes"] > 0
        assert s["ttl"] == 300
        assert s["max_entries"] == 100

    def test_stats_empty_cache(self, cache: Cache) -> None:
        s = cache.stats()
        assert s["enabled"] is True
        assert s["entries"] == 0
        assert s["total_size_bytes"] == 0

    def test_disabled_cache_returns_none(self, tmp_path: Path) -> None:
        config = CacheConfig(enabled=False, directory=str(tmp_path / "no-cache"))
        cache = Cache(config)

        chunks = [ContextChunk(content="data", source="s")]
        cache.put("source", "query", chunks)

        result = cache.get("source", "query")
        assert result is None

    def test_disabled_cache_stats(self, tmp_path: Path) -> None:
        config = CacheConfig(enabled=False, directory=str(tmp_path / "no-cache"))
        cache = Cache(config)

        s = cache.stats()
        assert s["enabled"] is False
        assert s["entries"] == 0

    def test_disabled_cache_invalidate(self, tmp_path: Path) -> None:
        config = CacheConfig(enabled=False, directory=str(tmp_path / "no-cache"))
        cache = Cache(config)
        count = cache.invalidate()
        assert count == 0

    def test_corrupt_entry_removed(self, cache: Cache, cache_dir: Path) -> None:
        # Write a corrupt JSON file
        key = Cache._key("docs", "query")
        corrupt_path = cache_dir / f"{key}.json"
        corrupt_path.write_text("not valid json{{{", encoding="utf-8")

        result = cache.get("docs", "query")
        assert result is None

        # The corrupt file should have been removed
        assert not corrupt_path.exists()

    def test_different_queries_have_different_keys(
        self, cache: Cache, sample_chunks: list[ContextChunk]
    ) -> None:
        cache.put("docs", "query1", sample_chunks[:1])
        cache.put("docs", "query2", sample_chunks[1:])

        r1 = cache.get("docs", "query1")
        r2 = cache.get("docs", "query2")

        assert r1 is not None
        assert r2 is not None
        assert r1[0].content != r2[0].content
