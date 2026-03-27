"""Disk-based cache with TTL for context chunks."""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

from theaios.context_router.types import CacheConfig, ContextChunk


class Cache:
    """Disk-based cache for context source results.

    Stores serialized chunks as JSON files in a cache directory.
    Each entry has a TTL and is evicted on read if expired.

    Parameters
    ----------
    config : CacheConfig
        Cache configuration (directory, TTL, max entries).
    """

    def __init__(self, config: CacheConfig) -> None:
        self._config = config
        self._dir = Path(config.directory)
        if config.enabled:
            self._dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _key(source: str, query_text: str) -> str:
        """Generate a SHA-256 cache key from source name and query text."""
        raw = f"{source}:{query_text}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def _entry_path(self, key: str) -> Path:
        """Return the file path for a cache entry."""
        return self._dir / f"{key}.json"

    def get(self, source: str, query_text: str) -> list[ContextChunk] | None:
        """Retrieve cached chunks for a source + query.

        Returns None if not cached or if the entry has expired.

        Parameters
        ----------
        source : str
            The source name.
        query_text : str
            The query text.

        Returns
        -------
        list[ContextChunk] | None
            Cached chunks, or None if miss/expired.
        """
        if not self._config.enabled:
            return None

        key = self._key(source, query_text)
        path = self._entry_path(key)

        if not path.exists():
            return None

        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            # Corrupt entry — remove it
            path.unlink(missing_ok=True)
            return None

        # Check TTL
        cached_at = raw.get("cached_at", 0)
        if time.time() - cached_at > self._config.ttl:
            path.unlink(missing_ok=True)
            return None

        # Deserialize chunks
        chunks: list[ContextChunk] = []
        for item in raw.get("chunks", []):
            chunks.append(
                ContextChunk(
                    content=str(item.get("content", "")),
                    source=str(item.get("source", "")),
                    title=str(item.get("title", "")),
                    path=str(item.get("path", "")),
                    relevance_score=float(item.get("relevance_score", 0.0)),
                    token_count=int(item.get("token_count", 0)),
                    metadata=dict(item.get("metadata", {})),
                )
            )
        return chunks

    def put(self, source: str, query_text: str, chunks: list[ContextChunk]) -> None:
        """Store chunks in the cache.

        Parameters
        ----------
        source : str
            The source name.
        query_text : str
            The query text.
        chunks : list[ContextChunk]
            Chunks to cache.
        """
        if not self._config.enabled:
            return

        # Enforce max entries by evicting oldest
        self._enforce_max_entries()

        key = self._key(source, query_text)
        path = self._entry_path(key)

        serialized = {
            "cached_at": time.time(),
            "source": source,
            "query_text": query_text,
            "chunks": [
                {
                    "content": chunk.content,
                    "source": chunk.source,
                    "title": chunk.title,
                    "path": chunk.path,
                    "relevance_score": chunk.relevance_score,
                    "token_count": chunk.token_count,
                    "metadata": chunk.metadata,
                }
                for chunk in chunks
            ],
        }

        path.write_text(json.dumps(serialized, default=str), encoding="utf-8")

    def invalidate(self, source: str | None = None) -> int:
        """Remove cache entries.

        Parameters
        ----------
        source : str | None
            If provided, only invalidate entries for this source.
            If None, clear all entries.

        Returns
        -------
        int
            Number of entries removed.
        """
        if not self._config.enabled or not self._dir.exists():
            return 0

        count = 0
        for path in self._dir.glob("*.json"):
            if source is not None:
                try:
                    raw = json.loads(path.read_text(encoding="utf-8"))
                    if raw.get("source") != source:
                        continue
                except (json.JSONDecodeError, OSError):
                    pass
            path.unlink(missing_ok=True)
            count += 1

        return count

    def stats(self) -> dict[str, object]:
        """Return cache statistics.

        Returns
        -------
        dict[str, object]
            Statistics including entry count, total size, and directory.
        """
        if not self._config.enabled or not self._dir.exists():
            return {
                "enabled": self._config.enabled,
                "entries": 0,
                "total_size_bytes": 0,
                "directory": str(self._dir),
                "ttl": self._config.ttl,
                "max_entries": self._config.max_entries,
            }

        entries = list(self._dir.glob("*.json"))
        total_size = sum(p.stat().st_size for p in entries if p.exists())

        return {
            "enabled": self._config.enabled,
            "entries": len(entries),
            "total_size_bytes": total_size,
            "directory": str(self._dir),
            "ttl": self._config.ttl,
            "max_entries": self._config.max_entries,
        }

    def _enforce_max_entries(self) -> None:
        """Evict oldest entries if cache exceeds max_entries."""
        if not self._dir.exists():
            return

        entries = sorted(self._dir.glob("*.json"), key=lambda p: p.stat().st_mtime)

        # Leave room for one new entry
        while len(entries) >= self._config.max_entries:
            oldest = entries.pop(0)
            oldest.unlink(missing_ok=True)
