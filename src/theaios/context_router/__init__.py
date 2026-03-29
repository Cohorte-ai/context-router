"""theaios-context-router — Intelligent context routing for AI agents."""

from __future__ import annotations

__version__ = "0.2.1"

from theaios.context_router.config import ConfigError, load_config
from theaios.context_router.engine import Router
from theaios.context_router.sources import Source, get_source, list_sources, register_source
from theaios.context_router.types import (
    BudgetConfig,
    CacheConfig,
    ContextChunk,
    ContextResponse,
    DefaultPermission,
    EmbeddingConfig,
    PermissionConfig,
    Query,
    Ranking,
    RouteConfig,
    RouterConfig,
    RouterMetadata,
    SourceConfig,
    SourceType,
    TokenEstimator,
    Truncation,
)


def query(
    config_path: str = "context-router.yaml",
    *,
    text: str,
    agent: str = "default",
    **metadata: object,
) -> ContextResponse:
    """One-liner: load config, build query, route."""
    config = load_config(config_path)
    router = Router(config)
    q = Query(text=text, agent=agent, metadata=dict(metadata))
    return router.query(q)


__all__ = [
    # Core
    "Router",
    "load_config",
    "query",
    "ConfigError",
    # Types — enums
    "SourceType",
    "Ranking",
    "Truncation",
    "DefaultPermission",
    "TokenEstimator",
    # Types — config
    "SourceConfig",
    "RouteConfig",
    "PermissionConfig",
    "BudgetConfig",
    "CacheConfig",
    "EmbeddingConfig",
    "RouterMetadata",
    "RouterConfig",
    # Types — runtime
    "Query",
    "ContextChunk",
    "ContextResponse",
    # Source registry
    "Source",
    "register_source",
    "get_source",
    "list_sources",
]
