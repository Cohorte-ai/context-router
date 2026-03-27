# Concepts

How theaios-context-router works under the hood.

---

## The Query Model

Everything starts with a **Query** -- a request from an AI agent that needs context.

```python
Query(
    text="What is the remote work policy?",   # What to search for
    agent="hr-assistant",                      # Who is asking
    tags=["onboarding"],                       # Optional labels
    metadata={"department": "engineering"},     # Optional key-value pairs
)
```

The `text` field is the primary input -- route conditions evaluate against it, and relevance scoring compares it to retrieved chunks. The `agent` field determines which permissions apply. Both `tags` and `metadata` are accessible in route expressions for fine-grained routing.

### What Goes in a Query

| Field | Type | Default | Purpose |
|-------|------|---------|---------|
| `text` | string | **(required)** | The query text. Used for route matching, relevance scoring, and API template substitution. |
| `agent` | string | `"default"` | Agent identifier. Matched against permission rules. |
| `tags` | list | `[]` | Labels accessible in route expressions as `tags`. |
| `metadata` | dict | `{}` | Key-value pairs accessible in route expressions by key name. |

---

## The Response Model

The engine returns a `ContextResponse` containing the assembled context:

```python
@dataclass
class ContextResponse:
    chunks: list[ContextChunk]      # The context pieces, ranked and trimmed
    total_tokens: int               # Total estimated tokens across all chunks
    was_truncated: bool             # True if budget trimming dropped or cut chunks
    matched_routes: list[str]       # Which routes matched the query
    denied_sources: list[str]       # Sources blocked by permissions
    evaluation_time_ms: float       # End-to-end pipeline time in milliseconds
    metadata: dict[str, object]     # Additional metadata
```

**Properties:**

| Property | Type | Description |
|----------|------|-------------|
| `text` | str | All chunks concatenated with double newlines. Ready to inject into a prompt. |
| `is_empty` | bool | True if no chunks were returned. |

### Context Chunks

Each chunk is a piece of context from a specific source:

```python
@dataclass
class ContextChunk:
    content: str                    # The actual text content
    source: str                     # Which source this came from
    title: str                      # Human-readable title (filename, heading, etc.)
    path: str                       # File path (for directory/git sources)
    relevance_score: float          # 0.0 to 1.0, how relevant to the query
    token_count: int                # Estimated token count
    metadata: dict[str, object]     # Source-specific metadata (mtime, ref, url, etc.)
```

---

## The 8-Stage Pipeline

When `router.query(q)` is called, the engine executes eight stages in sequence:

```
Query arrives
    |
    +-- 1. Route Matching
    |     Evaluate route conditions against the query.
    |     Which sources should be consulted?
    |
    +-- 2. Permission Filtering
    |     Check the agent's permissions.
    |     Which of those sources is this agent allowed to access?
    |
    +-- 3. Parallel Fetch
    |     Fetch chunks from all allowed sources concurrently.
    |     Check cache first; store results after fetch.
    |
    +-- 4. Path Filtering
    |     Remove chunks whose file path matches any deny_paths pattern.
    |
    +-- 5. Relevance Scoring
    |     Score each chunk against the query using keyword overlap.
    |
    +-- 6. Ranking
    |     Sort chunks by the configured strategy (relevance, recency, or manual).
    |
    +-- 7. Budget Trimming
    |     Fit chunks within the token budget.
    |     Drop or truncate excess chunks.
    |
    +-- 8. Assembly
          Build the final ContextResponse with timing and metadata.
```

### Stage 1: Route Matching

Routes map query conditions to sources. Each route has a `when` expression that is evaluated against the query context:

```yaml
routes:
  - name: policy-questions
    when: 'text contains "policy"'
    sources: [company_docs]
```

The expression context includes:

- `text` -- the query text
- `agent` -- the agent identifier
- `tags` -- the query tags list
- Any keys from `query.metadata`
- Any `variables` defined in the config

Routes are evaluated top-to-bottom. **All matching routes contribute sources** -- this is not first-match-wins. If both `default` and `policy-questions` match, their source lists are merged (deduplicated).

An empty `when` clause always matches, making it useful for default routes.

### Stage 2: Permission Filtering

Once the engine knows which sources to consult, it checks whether the current agent is allowed to access each one.

Permission rules are evaluated in order. Rules matching the exact agent name and wildcard rules (`agent: "*"`) are merged. Deny lists are unioned, allow lists are unioned, and the most restrictive default wins.

The result: two lists -- allowed source names and denied source names. Denied sources are recorded in `response.denied_sources` for auditability.

### Stage 3: Parallel Fetch

The engine fetches from all allowed sources **concurrently** using `asyncio.gather()`. Each source type (inline, directory, git_repo, http_api) implements an async `fetch()` method.

Before fetching, the engine checks the disk cache. If a cached result exists and has not expired (TTL), the cached chunks are returned without re-fetching.

If any individual source raises an exception, it is silently skipped -- the remaining sources still return their results. This makes the pipeline resilient to transient failures.

### Stage 4: Path Filtering

After fetching, any chunks whose `path` field matches a `deny_paths` glob pattern are removed. This provides file-level access control on top of source-level permissions. For example, you can allow an agent to access a docs directory while denying access to files matching `"**/secrets/**"`.

Chunks without a `path` (e.g., inline sources, API results) are never filtered by path.

### Stage 5: Relevance Scoring

Each chunk is scored against the query text using keyword overlap:

1. Both query and chunk text are tokenized (lowercased, punctuation stripped)
2. English stopwords are removed
3. Title keywords are included with the chunk keywords
4. The score is the fraction of query keywords found in the chunk (Jaccard-like, weighted toward query coverage)

The score ranges from 0.0 (no overlap) to 1.0 (all query keywords found). This is a lightweight, dependency-free scoring method -- no embeddings or vector databases required.

### Stage 6: Ranking

Chunks are sorted by the configured ranking strategy:

| Strategy | Sort key | Use case |
|----------|----------|----------|
| `relevance` | `relevance_score` (descending) | Best for search-like queries. Default. |
| `recency` | `metadata.mtime` (descending) | Best for "what changed recently" queries. |
| `manual` | Insertion order (preserved) | Best when source priority controls ordering. |

### Stage 7: Budget Trimming

The ranked chunks are fitted within the token budget. The engine processes chunks in order, adding each one until the budget is exhausted.

When a chunk exceeds the remaining budget, the truncation strategy determines what happens:

| Strategy | Behavior |
|----------|----------|
| `drop` | Skip the chunk entirely. The safest option -- no partial content. |
| `truncate_end` | Cut the chunk from the end to fit. Appends `[...]`. |
| `truncate_middle` | Keep the beginning and end, cut the middle. Inserts `[...truncated...]`. |

The `reserve_tokens` setting reserves a portion of the budget (e.g., for a system prompt injected separately). The effective budget is `max_tokens - reserve_tokens`.

### Stage 8: Assembly

The kept chunks are packaged into a `ContextResponse` with:

- Total token count across all chunks
- Whether any truncation occurred
- Which routes matched
- Which sources were denied by permissions
- End-to-end evaluation time in milliseconds

---

## Source Types

Sources are where context lives. The engine ships with four built-in source types:

| Source | What it does | When to use |
|--------|-------------|-------------|
| `inline` | Returns static text from the config | System prompts, instructions, boilerplate |
| `directory` | Reads files from a local directory | Documentation, knowledge bases, config files |
| `git_repo` | Reads files from a git ref | Versioned docs, historical content, branch-specific context |
| `http_api` | Queries a REST API | Search APIs, knowledge services, external data |

All sources implement the same `Source` base class and `fetch()` async method. Custom sources can be registered with the `@register_source` decorator.

See [Source Types](sources.md) for details on each built-in source and how to write your own.

---

## Caching

The engine includes an optional disk-based cache with TTL. When enabled, source fetch results are cached to avoid redundant I/O.

```yaml
cache:
  enabled: true
  directory: ".context-router-cache"
  ttl: 300          # seconds
  max_entries: 1000
```

Cache keys are generated from the source name and query text (SHA-256 hash). Entries are stored as JSON files. Expired entries are evicted on read. When `max_entries` is reached, the oldest entries are evicted on write.

The cache operates at the source level -- if a query matches routes that hit sources A, B, and C, each source's results are cached independently. A cache hit for source A does not affect fetching from B and C.

Cache management commands:

```bash
context-router cache stats --config context-router.yaml
context-router cache clear --config context-router.yaml
context-router cache clear --config context-router.yaml --source docs
```

---

## Environment Variable Interpolation

String values in the YAML config can reference environment variables using `${VAR_NAME}` syntax:

```yaml
sources:
  api:
    type: http_api
    url: "https://api.example.com/search"
    headers:
      Authorization: "Bearer ${API_TOKEN}"
```

If the environment variable is not set, the placeholder is left as-is (not expanded). Interpolation is applied recursively to all string values in the config before parsing.

---

## Performance

The engine is designed for inline use -- it sits in the path between your agent and its LLM call.

| Metric | Value |
|--------|-------|
| Route evaluation | <0.1ms for 10 routes |
| Parallel fetch overhead | Bounded by slowest source |
| Relevance scoring | ~0.01ms per chunk |
| Budget trimming | ~0.01ms for 100 chunks |
| Memory (loaded config) | ~50KB for typical configs |
| Dependencies | 5 (pyyaml, click, rich, httpx, aiofiles) |

This is fast because:

- All route expressions are **pre-compiled** into ASTs when the `Router` is created
- Source fetching is **async and parallel** -- all sources are fetched concurrently
- Relevance scoring uses **keyword overlap** -- no embeddings, no model calls
- Budget trimming is a **single pass** through the ranked list
- The disk cache avoids redundant I/O for repeated queries

For comparison, RAG pipelines that call an embedding model add 50-200ms per query for vectorization. This engine adds <1ms for routing + scoring, with fetch time bounded by your data sources.
