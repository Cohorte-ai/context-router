"""Shared data models for the Context Router engine."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class SourceType(Enum):
    """Built-in source types."""

    INLINE = "inline"
    DIRECTORY = "directory"
    GIT_REPO = "git_repo"
    HTTP_API = "http_api"


class Ranking(Enum):
    """How to rank context chunks before budget trimming."""

    RELEVANCE = "relevance"
    RECENCY = "recency"
    MANUAL = "manual"


class Truncation(Enum):
    """How to truncate chunks that exceed the token budget."""

    DROP = "drop"
    TRUNCATE_END = "truncate_end"
    TRUNCATE_MIDDLE = "truncate_middle"


class DefaultPermission(Enum):
    """Default permission when no explicit rule matches."""

    ALLOW = "allow"
    DENY = "deny"


class TokenEstimator(Enum):
    """Token estimation methods."""

    CHARS_DIV4 = "chars_div4"
    WORDS = "words"
    WHITESPACE = "whitespace"


# ---------------------------------------------------------------------------
# Validation sets
# ---------------------------------------------------------------------------

VALID_SOURCE_TYPES = {s.value for s in SourceType}
VALID_RANKINGS = {r.value for r in Ranking}
VALID_TRUNCATIONS = {t.value for t in Truncation}
VALID_DEFAULT_PERMISSIONS = {p.value for p in DefaultPermission}
VALID_TOKEN_ESTIMATORS = {e.value for e in TokenEstimator}


# ---------------------------------------------------------------------------
# Configuration (parsed from YAML)
# ---------------------------------------------------------------------------


@dataclass
class SourceConfig:
    """Configuration for a single context source."""

    name: str
    type: str
    enabled: bool = True
    description: str = ""

    # Source-specific fields
    path: str = ""
    content: str = ""
    url: str = ""
    ref: str = "HEAD"
    method: str = "GET"
    headers: dict[str, str] = field(default_factory=dict)
    body_template: str = ""
    response_path: str = ""
    result_text_field: str = "text"
    result_title_field: str = "title"

    # File matching
    patterns: list[str] = field(default_factory=lambda: ["**/*"])
    exclude_patterns: list[str] = field(default_factory=list)
    recursive: bool = True
    encoding: str = "utf-8"
    max_file_size: int = 1_000_000  # bytes

    # Metadata
    tags: list[str] = field(default_factory=list)
    priority: int = 0


@dataclass
class RouteConfig:
    """A route maps a query condition to one or more sources."""

    name: str
    when: str = ""
    sources: list[str] = field(default_factory=list)
    description: str = ""
    enabled: bool = True
    tags: list[str] = field(default_factory=list)


@dataclass
class PermissionConfig:
    """Permission rules for agents accessing context sources."""

    agent: str = "*"
    allow_sources: list[str] = field(default_factory=list)
    deny_sources: list[str] = field(default_factory=list)
    deny_paths: list[str] = field(default_factory=list)
    default: str = "allow"


@dataclass
class BudgetConfig:
    """Token budget configuration."""

    max_tokens: int = 8000
    ranking: str = "relevance"
    truncation: str = "drop"
    estimator: str = "chars_div4"
    reserve_tokens: int = 0


@dataclass
class CacheConfig:
    """Disk cache configuration."""

    enabled: bool = False
    directory: str = ".context-router-cache"
    ttl: int = 300  # seconds
    max_entries: int = 1000


@dataclass
class RouterMetadata:
    """Router-level metadata."""

    name: str = ""
    description: str = ""
    author: str = ""


@dataclass
class RouterConfig:
    """Top-level router configuration — maps 1:1 to context-router.yaml."""

    version: str = "1.0"
    metadata: RouterMetadata = field(default_factory=RouterMetadata)
    variables: dict[str, object] = field(default_factory=dict)
    sources: dict[str, SourceConfig] = field(default_factory=dict)
    routes: list[RouteConfig] = field(default_factory=list)
    permissions: list[PermissionConfig] = field(default_factory=list)
    budget: BudgetConfig = field(default_factory=BudgetConfig)
    cache: CacheConfig = field(default_factory=CacheConfig)


# ---------------------------------------------------------------------------
# Runtime types
# ---------------------------------------------------------------------------


@dataclass
class Query:
    """A query to evaluate against the router."""

    text: str
    agent: str = "default"
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass
class ContextChunk:
    """A single piece of context retrieved from a source."""

    content: str
    source: str
    title: str = ""
    path: str = ""
    relevance_score: float = 0.0
    token_count: int = 0
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass
class ContextResponse:
    """Result of routing a query through the context engine."""

    chunks: list[ContextChunk] = field(default_factory=list)
    total_tokens: int = 0
    was_truncated: bool = False
    matched_routes: list[str] = field(default_factory=list)
    denied_sources: list[str] = field(default_factory=list)
    evaluation_time_ms: float = 0.0
    metadata: dict[str, object] = field(default_factory=dict)

    @property
    def text(self) -> str:
        """Concatenate all chunks into a single string."""
        return "\n\n".join(c.content for c in self.chunks)

    @property
    def is_empty(self) -> bool:
        """True if no chunks were returned."""
        return len(self.chunks) == 0
