"""Source base class, registry, and built-in sources."""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from typing import Any

from theaios.context_router.types import ContextChunk, Query, SourceConfig


# ---------------------------------------------------------------------------
# Base class
# ---------------------------------------------------------------------------


class Source(ABC):
    """Base class for all context sources.

    A source fetches context chunks from an external data store
    (files, APIs, git repos, etc.) and returns them for routing.
    """

    @abstractmethod
    async def fetch(self, query: Query, config: SourceConfig) -> list[ContextChunk]:
        """Fetch context chunks from this source.

        Parameters
        ----------
        query : Query
            The incoming query with text and metadata.
        config : SourceConfig
            Source-specific configuration from the router config.

        Returns
        -------
        list[ContextChunk]
            Zero or more context chunks retrieved from the source.
        """

    def fetch_sync(self, query: Query, config: SourceConfig) -> list[ContextChunk]:
        """Synchronous wrapper around ``fetch()``.

        Uses ``asyncio.run()`` to execute the async fetch in a new event loop.
        If an event loop is already running, falls back to creating a new thread.
        """
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop is not None:
            # Already inside an async context — run in a new thread
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(asyncio.run, self.fetch(query, config))
                return future.result()

        return asyncio.run(self.fetch(query, config))


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

_REGISTRY: dict[str, type[Source]] = {}


def register_source(name: str) -> Any:  # noqa: ANN401
    """Decorator to register a source class by name.

    Usage::

        @register_source("inline")
        class InlineSource(Source):
            ...
    """

    def decorator(cls: type[Source]) -> type[Source]:
        _REGISTRY[name] = cls
        return cls

    return decorator


def get_source(name: str) -> Source:
    """Instantiate a registered source by name."""
    if name not in _REGISTRY:
        available = sorted(_REGISTRY.keys())
        raise KeyError(f"Unknown source type '{name}'. Available: {available}")
    return _REGISTRY[name]()


def list_sources() -> list[str]:
    """Return all registered source type names."""
    return sorted(_REGISTRY.keys())


# ---------------------------------------------------------------------------
# Eagerly import built-in source modules so decorators run.
# ---------------------------------------------------------------------------
import theaios.context_router.sources.directory as _directory  # noqa: E402, F401
import theaios.context_router.sources.git_repo as _git_repo  # noqa: E402, F401
import theaios.context_router.sources.http_api as _http_api  # noqa: E402, F401
import theaios.context_router.sources.inline as _inline  # noqa: E402, F401
