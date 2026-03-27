# Python API Reference

## Core Functions

### `load_config(path) -> RouterConfig`

Load and validate a YAML config file. Returns a typed `RouterConfig` object.

```python
from theaios.context_router import load_config

config = load_config("context-router.yaml")
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `path` | str | `"context-router.yaml"` | Path to the YAML config file |

**Returns:** `RouterConfig` -- the parsed and validated configuration.

**Raises:**

- `FileNotFoundError` if the file does not exist
- `ConfigError` if validation fails (contains a list of error messages)

---

### `query(config_path, *, text, agent, **metadata) -> ContextResponse`

One-liner convenience function. Loads the config, builds a query, creates a router, and returns the response.

```python
from theaios.context_router import query

response = query("context-router.yaml", text="What is the PTO policy?")
response = query("context-router.yaml", text="Deploy guide", agent="eng-assistant")
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `config_path` | str | `"context-router.yaml"` | Path to the YAML config file |
| `text` | str | **(required)** | Query text |
| `agent` | str | `"default"` | Agent identifier |
| `**metadata` | object | -- | Additional metadata passed to the query |

**Returns:** `ContextResponse`

For repeated queries, prefer creating a `Router` instance once and reusing it -- this avoids re-parsing the config and re-compiling expressions on every call.

---

## Router

### `Router(config)`

The main context routing engine. Create once with a parsed config, then call `query()` or `query_async()` for each request.

```python
from theaios.context_router import Router, load_config

config = load_config("context-router.yaml")
router = Router(config)
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `config` | `RouterConfig` | A parsed router configuration from `load_config()` |

On construction, the router:

- Compiles all `when` expressions into ASTs
- Instantiates all source implementations from the registry
- Initializes the disk cache

This work happens once. Subsequent `query()` calls are pure computation + I/O.

**Raises:** `ExpressionError` if any route's `when` expression has a syntax error.

### `router.query(q) -> ContextResponse`

Execute a query synchronously. This is a wrapper around `query_async()` that handles the asyncio event loop.

```python
from theaios.context_router import Query

response = router.query(Query(text="What is the remote work policy?"))
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `q` | `Query` | The incoming query |

**Returns:** `ContextResponse`

If called from inside an async context (i.e., an event loop is already running), the method uses a thread pool to avoid blocking.

### `router.query_async(q) -> ContextResponse`

Execute a query asynchronously. Runs the full 8-stage pipeline: route matching, permission filtering, parallel fetch, path filtering, relevance scoring, ranking, budget trimming, and assembly.

```python
import asyncio
from theaios.context_router import Query

response = await router.query_async(Query(text="What is the remote work policy?"))
# or
response = asyncio.run(router.query_async(Query(text="What is the remote work policy?")))
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `q` | `Query` | The incoming query |

**Returns:** `ContextResponse`

### `router.config -> RouterConfig`

Property. Returns the loaded router configuration.

### `router.cache -> Cache`

Property. Returns the cache instance. Useful for programmatic cache management:

```python
stats = router.cache.stats()
router.cache.invalidate("docs")  # Clear cache for one source
router.cache.invalidate()        # Clear all cache
```

---

## Data Types

### `Query`

```python
@dataclass
class Query:
    text: str                               # The query text (required)
    agent: str = "default"                  # Agent identifier
    tags: list[str] = field(default_factory=list)        # Optional labels
    metadata: dict[str, object] = field(default_factory=dict)  # Optional key-value pairs
```

**Usage:**

```python
from theaios.context_router import Query

# Simple query
q = Query(text="What is the remote work policy?")

# Agent-specific query
q = Query(text="Show me project docs", agent="eng-assistant")

# Query with metadata (accessible in route expressions)
q = Query(
    text="Find onboarding guide",
    agent="hr-bot",
    tags=["onboarding"],
    metadata={"department": "engineering"},
)
```

### `ContextResponse`

```python
@dataclass
class ContextResponse:
    chunks: list[ContextChunk] = []         # Ranked and trimmed context chunks
    total_tokens: int = 0                   # Total estimated tokens
    was_truncated: bool = False             # True if budget trimming occurred
    matched_routes: list[str] = []          # Route names that matched
    denied_sources: list[str] = []          # Sources blocked by permissions
    evaluation_time_ms: float = 0.0         # Pipeline execution time (ms)
    metadata: dict[str, object] = {}        # Additional metadata
```

**Properties:**

| Property | Type | Description |
|----------|------|-------------|
| `text` | str | All chunks concatenated with `"\n\n"`. Ready to inject into a prompt. |
| `is_empty` | bool | True if no chunks were returned. |

**Usage:**

```python
response = router.query(Query(text="remote work policy"))

# Check if we got results
if response.is_empty:
    print("No context found")
else:
    print(f"Found {len(response.chunks)} chunks ({response.total_tokens} tokens)")
    print(f"Routes: {response.matched_routes}")
    print(f"Denied: {response.denied_sources}")
    print(f"Truncated: {response.was_truncated}")
    print(f"Time: {response.evaluation_time_ms:.2f}ms")

    # Get concatenated text for prompt injection
    context_text = response.text
```

### `ContextChunk`

```python
@dataclass
class ContextChunk:
    content: str                            # The text content
    source: str                             # Source name
    title: str = ""                         # Human-readable title
    path: str = ""                          # File path (for file-based sources)
    relevance_score: float = 0.0            # 0.0 to 1.0
    token_count: int = 0                    # Estimated token count
    metadata: dict[str, object] = {}        # Source-specific metadata
```

**Metadata keys by source type:**

| Source | Metadata keys |
|--------|--------------|
| `inline` | -- |
| `directory` | `mtime` (float, file modification timestamp) |
| `git_repo` | `ref` (string, git ref used) |
| `http_api` | `url` (string, the source URL) |

---

## Configuration Types

### `RouterConfig`

The top-level config object. Maps 1:1 to the YAML file structure.

```python
@dataclass
class RouterConfig:
    version: str = "1.0"
    metadata: RouterMetadata
    variables: dict[str, object]
    sources: dict[str, SourceConfig]        # Keyed by source name
    routes: list[RouteConfig]
    permissions: list[PermissionConfig]
    budget: BudgetConfig
    cache: CacheConfig
```

### `RouterMetadata`

```python
@dataclass
class RouterMetadata:
    name: str = ""
    description: str = ""
    author: str = ""
```

### `SourceConfig`

```python
@dataclass
class SourceConfig:
    name: str
    type: str                               # "inline", "directory", "git_repo", "http_api"
    enabled: bool = True
    description: str = ""

    # Source-specific fields
    path: str = ""                          # directory, git_repo
    content: str = ""                       # inline
    url: str = ""                           # http_api
    ref: str = "HEAD"                       # git_repo
    method: str = "GET"                     # http_api
    headers: dict[str, str] = {}            # http_api
    body_template: str = ""                 # http_api
    response_path: str = ""                 # http_api
    result_text_field: str = "text"         # http_api
    result_title_field: str = "title"       # http_api

    # File matching (directory, git_repo)
    patterns: list[str] = ["**/*"]
    exclude_patterns: list[str] = []
    recursive: bool = True
    encoding: str = "utf-8"
    max_file_size: int = 1_000_000

    # Metadata
    tags: list[str] = []
    priority: int = 0
```

### `RouteConfig`

```python
@dataclass
class RouteConfig:
    name: str
    when: str = ""                          # Expression. Empty = always matches.
    sources: list[str] = []                 # Source names
    description: str = ""
    enabled: bool = True
    tags: list[str] = []
```

### `PermissionConfig`

```python
@dataclass
class PermissionConfig:
    agent: str = "*"                        # "*" = wildcard
    allow_sources: list[str] = []
    deny_sources: list[str] = []
    deny_paths: list[str] = []             # Glob patterns
    default: str = "allow"                  # "allow" or "deny"
```

### `BudgetConfig`

```python
@dataclass
class BudgetConfig:
    max_tokens: int = 8000
    ranking: str = "relevance"              # "relevance", "recency", "manual"
    truncation: str = "drop"                # "drop", "truncate_end", "truncate_middle"
    estimator: str = "chars_div4"           # "chars_div4", "words", "whitespace"
    reserve_tokens: int = 0
```

### `CacheConfig`

```python
@dataclass
class CacheConfig:
    enabled: bool = False
    directory: str = ".context-router-cache"
    ttl: int = 300                          # seconds
    max_entries: int = 1000
```

---

## Enums

All enums use string values that match the YAML config values:

```python
from theaios.context_router import SourceType, Ranking, Truncation, DefaultPermission, TokenEstimator

SourceType.INLINE          # "inline"
SourceType.DIRECTORY       # "directory"
SourceType.GIT_REPO        # "git_repo"
SourceType.HTTP_API        # "http_api"

Ranking.RELEVANCE          # "relevance"
Ranking.RECENCY            # "recency"
Ranking.MANUAL             # "manual"

Truncation.DROP            # "drop"
Truncation.TRUNCATE_END    # "truncate_end"
Truncation.TRUNCATE_MIDDLE # "truncate_middle"

DefaultPermission.ALLOW    # "allow"
DefaultPermission.DENY     # "deny"

TokenEstimator.CHARS_DIV4  # "chars_div4"
TokenEstimator.WORDS       # "words"
TokenEstimator.WHITESPACE  # "whitespace"
```

---

## Source Registry

### `register_source(name)`

Decorator to register a custom source class.

```python
from theaios.context_router import Source, register_source

@register_source("my_source")
class MySource(Source):
    async def fetch(self, query, config):
        return [ContextChunk(content="hello", source=config.name)]
```

### `get_source(name) -> Source`

Instantiate a registered source by type name.

```python
from theaios.context_router import get_source

source = get_source("inline")
```

**Raises:** `KeyError` if the source type is not registered.

### `list_sources() -> list[str]`

Return all registered source type names.

```python
from theaios.context_router import list_sources

names = list_sources()  # ["directory", "git_repo", "http_api", "inline"]
```

---

## Exceptions

| Exception | Module | When |
|-----------|--------|------|
| `ConfigError` | `theaios.context_router.config` | Config file is invalid. Has an `errors` attribute (list of strings). |
| `ExpressionError` | `theaios.context_router.expressions` | Expression cannot be parsed or evaluated. Has `source` and `pos` attributes. |

```python
from theaios.context_router import ConfigError, load_config

try:
    config = load_config("broken.yaml")
except ConfigError as e:
    for error in e.errors:
        print(f"  - {error}")
```

---

## Complete Example

```python
from theaios.context_router import Router, load_config, Query

# Load config once
config = load_config("context-router.yaml")
router = Router(config)

# Query for different agents
for agent in ["hr-bot", "eng-assistant", "intern-bot"]:
    response = router.query(Query(
        text="What is the remote work policy?",
        agent=agent,
    ))

    print(f"\n--- Agent: {agent} ---")
    print(f"Matched routes: {response.matched_routes}")
    print(f"Denied sources: {response.denied_sources}")
    print(f"Chunks: {len(response.chunks)} ({response.total_tokens} tokens)")
    print(f"Truncated: {response.was_truncated}")
    print(f"Time: {response.evaluation_time_ms:.2f}ms")

    for chunk in response.chunks:
        print(f"  [{chunk.source}] {chunk.title} "
              f"(score={chunk.relevance_score:.2f}, tokens={chunk.token_count})")
```
