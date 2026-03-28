"""Context Router engine — the main routing pipeline.

Matches routes, resolves permissions, fetches from sources in parallel,
scores relevance, ranks, applies budget, and assembles the final response.
"""

from __future__ import annotations

import asyncio
import time

from theaios.context_router.budget import (
    apply_budget,
    estimate_tokens,
    rank_chunks,
    score_relevance,
)
from theaios.context_router.cache import Cache
from theaios.context_router.expressions import (
    ASTNode,
    ExpressionError,
    compile_expression,
    evaluate as eval_expr,
)
from theaios.context_router.permissions import (
    filter_by_path,
    filter_by_source,
    resolve_permission,
)
from theaios.context_router.sources import Source, get_source
from theaios.context_router.types import (
    ContextChunk,
    ContextResponse,
    Query,
    RouterConfig,
    SourceConfig,
)


class Router:
    """Context Router engine.

    Orchestrates the full context retrieval pipeline:
    route matching -> permission filtering -> parallel fetch ->
    path filtering -> relevance scoring -> ranking -> budget trimming.

    Parameters
    ----------
    config : RouterConfig
        A parsed router configuration from ``load_config()``.
    """

    def __init__(self, config: RouterConfig) -> None:
        self._config = config

        # Compile route expressions
        self._compiled_routes: list[tuple[str, list[str], ASTNode]] = []
        for route in config.routes:
            if not route.enabled:
                continue
            try:
                ast = compile_expression(route.when)
            except ExpressionError as e:
                raise ExpressionError(
                    f"Error in route '{route.name}': {e}",
                ) from e
            self._compiled_routes.append((route.name, route.sources, ast))

        # Instantiate source implementations
        self._sources: dict[str, Source] = {}
        for name, source_config in config.sources.items():
            if source_config.enabled:
                self._sources[name] = get_source(source_config.type)

        # Initialize cache
        self._cache = Cache(config.cache)

        # Initialize embedding scorer if ranking is "embedding"
        self._embedding_scorer: object | None = None
        if config.budget.ranking == "embedding":
            if config.budget.embedding is None:
                raise ValueError(
                    "budget.ranking is 'embedding' but budget.embedding is not configured. "
                    "Add an embedding section to your budget config."
                )
            from theaios.context_router.embedding import EmbeddingScorer

            self._embedding_scorer = EmbeddingScorer(config.budget.embedding)

    @property
    def config(self) -> RouterConfig:
        """The loaded router configuration."""
        return self._config

    @property
    def cache(self) -> Cache:
        """The cache instance."""
        return self._cache

    def query(self, q: Query) -> ContextResponse:
        """Execute a query through the routing pipeline (sync wrapper).

        Parameters
        ----------
        q : Query
            The incoming query.

        Returns
        -------
        ContextResponse
            The assembled context response.
        """
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop is not None:
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(asyncio.run, self.query_async(q))
                return future.result()

        return asyncio.run(self.query_async(q))

    async def query_async(self, q: Query) -> ContextResponse:
        """Execute a query through the full routing pipeline.

        Pipeline stages:
        1. Route matching — evaluate route conditions against query
        2. Permission filtering — check agent permissions on matched sources
        3. Parallel fetch — fetch chunks from all allowed sources concurrently
        4. Path filtering — remove chunks matching deny_paths
        5. Relevance scoring — score each chunk against the query
        6. Ranking — sort chunks by configured strategy
        7. Budget trimming — fit chunks within token budget
        8. Assembly — build the final ContextResponse

        Parameters
        ----------
        q : Query
            The incoming query.

        Returns
        -------
        ContextResponse
            The assembled context response.
        """
        start = time.perf_counter()

        # 1. Route matching
        matched_sources: list[str] = []
        matched_routes: list[str] = []

        # Build context for expression evaluation
        expr_context: dict[str, object] = {
            "text": q.text,
            "agent": q.agent,
            "tags": q.tags,
        }
        expr_context.update({str(k): v for k, v in q.metadata.items()})

        for route_name, route_sources, ast in self._compiled_routes:
            try:
                result = eval_expr(
                    ast,
                    context=expr_context,
                    variables=self._config.variables,
                )
            except ExpressionError:
                continue

            if result:
                matched_routes.append(route_name)
                for sname in route_sources:
                    if sname not in matched_sources:
                        matched_sources.append(sname)

        # If no routes matched, return empty
        if not matched_sources:
            elapsed = (time.perf_counter() - start) * 1000
            return ContextResponse(
                matched_routes=matched_routes,
                evaluation_time_ms=elapsed,
            )

        # 2. Permission filtering
        permission = resolve_permission(q.agent, self._config.permissions)
        source_configs = {
            name: self._config.sources[name]
            for name in matched_sources
            if name in self._config.sources
        }
        allowed_names, denied_names = filter_by_source(source_configs, permission)

        # 3. Parallel fetch from allowed sources
        all_chunks: list[ContextChunk] = []

        async def _fetch_source(name: str, cfg: SourceConfig) -> list[ContextChunk]:
            # Check cache first
            cached = self._cache.get(name, q.text)
            if cached is not None:
                return cached

            source = self._sources.get(name)
            if source is None:
                return []

            chunks = await source.fetch(q, cfg)

            # Store in cache
            self._cache.put(name, q.text, chunks)

            return chunks

        tasks = []
        for name in allowed_names:
            if name in self._config.sources and name in self._sources:
                cfg = self._config.sources[name]
                tasks.append(_fetch_source(name, cfg))

        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for result in results:
                if isinstance(result, list):
                    all_chunks.extend(result)
                # Silently skip exceptions from individual sources

        # 4. Path filtering
        all_chunks = filter_by_path(all_chunks, permission.deny_paths)

        # 5. Relevance scoring
        if self._embedding_scorer is not None:
            # Embedding-based scoring (optional, requires API)
            from theaios.context_router.embedding import EmbeddingScorer

            scorer: EmbeddingScorer = self._embedding_scorer  # type: ignore[assignment]
            scores = scorer.score_batch(q.text, all_chunks)
            for chunk, score in zip(all_chunks, scores):
                chunk.relevance_score = score
                if chunk.token_count == 0:
                    chunk.token_count = estimate_tokens(
                        chunk.content, self._config.budget.estimator
                    )
        else:
            # Default: keyword overlap scoring (free, deterministic)
            for chunk in all_chunks:
                chunk.relevance_score = score_relevance(q.text, chunk)
                if chunk.token_count == 0:
                    chunk.token_count = estimate_tokens(
                        chunk.content, self._config.budget.estimator
                    )

        # 6. Ranking (embedding mode still uses "relevance" sorting — by score desc)
        ranking = (
            "relevance"
            if self._config.budget.ranking == "embedding"
            else self._config.budget.ranking
        )
        all_chunks = rank_chunks(all_chunks, ranking)

        # 7. Budget trimming
        kept_chunks, was_truncated = apply_budget(
            all_chunks,
            self._config.budget.max_tokens,
            truncation=self._config.budget.truncation,
            reserve_tokens=self._config.budget.reserve_tokens,
            estimator=self._config.budget.estimator,
        )

        # 8. Assembly
        total_tokens = sum(c.token_count for c in kept_chunks)
        elapsed = (time.perf_counter() - start) * 1000

        return ContextResponse(
            chunks=kept_chunks,
            total_tokens=total_tokens,
            was_truncated=was_truncated,
            matched_routes=matched_routes,
            denied_sources=denied_names,
            evaluation_time_ms=elapsed,
        )
