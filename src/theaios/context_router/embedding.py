"""Embedding-based relevance scoring.

Optional feature — requires ``pip install theaios-context-router[embeddings]``.
Uses the OpenAI embeddings API (or any compatible endpoint) to compute
semantic similarity between queries and document chunks.

Embeddings are cached on disk to avoid recomputation.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

from theaios.context_router.types import ContextChunk, EmbeddingConfig

try:
    import httpx
    import numpy as np

    _HAS_NUMPY = True
except ImportError:
    _HAS_NUMPY = False


class EmbeddingScorer:
    """Score chunk relevance using embedding cosine similarity.

    Caches document embeddings on disk so they are only computed once.
    Query embeddings are cached in memory per session.

    Parameters
    ----------
    config : EmbeddingConfig
        Embedding model and API configuration.
    """

    def __init__(self, config: EmbeddingConfig) -> None:
        if not _HAS_NUMPY:
            raise ImportError(
                "Embedding scoring requires numpy. "
                "Install with: pip install theaios-context-router[embeddings]"
            )

        self._config = config
        self._api_key = os.environ.get(config.api_key_env, "")
        if not self._api_key:
            raise ValueError(
                f"Environment variable '{config.api_key_env}' is not set. "
                "Set it to your OpenAI API key (or compatible provider)."
            )

        self._cache_dir = Path(config.cache_dir)
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        self._query_cache: dict[str, list[float]] = {}

    def score(self, query_text: str, chunk: ContextChunk) -> float:
        """Compute cosine similarity between query and chunk embeddings.

        Returns a float in [0.0, 1.0].
        """
        query_emb = self._get_query_embedding(query_text)
        chunk_emb = self._get_chunk_embedding(chunk)

        q = np.array(query_emb)
        d = np.array(chunk_emb)
        norm_q = np.linalg.norm(q)
        norm_d = np.linalg.norm(d)
        if norm_q == 0 or norm_d == 0:
            return 0.0

        similarity = float(np.dot(q, d) / (norm_q * norm_d))
        return max(0.0, similarity)

    def score_batch(self, query_text: str, chunks: list[ContextChunk]) -> list[float]:
        """Score multiple chunks against a query. More efficient than calling score() in a loop."""
        if not chunks:
            return []

        query_emb = np.array(self._get_query_embedding(query_text))
        norm_q = float(np.linalg.norm(query_emb))
        if norm_q == 0:
            return [0.0] * len(chunks)

        scores: list[float] = []
        for chunk in chunks:
            chunk_emb = np.array(self._get_chunk_embedding(chunk))
            norm_d = float(np.linalg.norm(chunk_emb))
            if norm_d == 0:
                scores.append(0.0)
            else:
                sim = float(np.dot(query_emb, chunk_emb) / (norm_q * norm_d))
                scores.append(max(0.0, sim))

        return scores

    def _get_query_embedding(self, text: str) -> list[float]:
        """Get embedding for a query (cached in memory)."""
        if text not in self._query_cache:
            self._query_cache[text] = self._embed(text)
        return self._query_cache[text]

    def _get_chunk_embedding(self, chunk: ContextChunk) -> list[float]:
        """Get embedding for a chunk (cached on disk)."""
        cache_key = self._chunk_cache_key(chunk)
        cache_path = self._cache_dir / f"{cache_key}.json"

        if cache_path.exists():
            try:
                data = json.loads(cache_path.read_text(encoding="utf-8"))
                return list(data["embedding"])
            except (json.JSONDecodeError, KeyError):
                pass

        # Truncate content for embedding (most models have a token limit)
        text = f"{chunk.title}\n{chunk.content}"[:8000]
        embedding = self._embed(text)

        # Cache to disk
        cache_path.write_text(
            json.dumps({"embedding": embedding}, ensure_ascii=False),
            encoding="utf-8",
        )

        return embedding

    def _embed(self, text: str) -> list[float]:
        """Call the embedding API for a single text."""
        with httpx.Client(timeout=30) as client:
            response = client.post(
                self._config.url,
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self._config.model,
                    "input": [text],
                },
            )
            response.raise_for_status()
            data = response.json()
            return list(data["data"][0]["embedding"])

    def _chunk_cache_key(self, chunk: ContextChunk) -> str:
        """Generate a cache key for a chunk based on its content."""
        raw = f"{self._config.model}:{chunk.source}:{chunk.title}:{chunk.content[:500]}"
        return hashlib.sha256(raw.encode()).hexdigest()[:24]

    def clear_cache(self) -> int:
        """Clear the embedding cache. Returns number of entries removed."""
        count = 0
        for f in self._cache_dir.glob("*.json"):
            f.unlink()
            count += 1
        return count
