# Source Types

Sources are where context lives. The context router fetches data from sources, scores it for relevance, and assembles it into a response. This page covers every built-in source type and how to write your own.

---

## Overview

| Source | What it does | Key fields | Best for |
|--------|-------------|------------|----------|
| `inline` | Returns static text from config | `content` | System prompts, instructions, boilerplate |
| `directory` | Reads files from a local directory | `path`, `patterns` | Documentation, knowledge bases |
| `git_repo` | Reads files from a git ref | `path`, `ref`, `patterns` | Versioned docs, branch-specific context |
| `http_api` | Queries a REST API | `url`, `method`, `body_template` | Search APIs, knowledge services |

All sources implement the `Source` base class and its async `fetch()` method. Sources are fetched **in parallel** -- if a query matches routes pointing to three sources, all three are fetched concurrently.

---

## `inline` -- Static Content

The simplest source type. Returns the `content` field as a single context chunk. No I/O, no latency.

### Config

```yaml
sources:
  system_prompt:
    type: inline
    content: |
      You are an AI assistant for ACME Corp.
      Be helpful, accurate, and concise.
      Always cite the source of your information.
    priority: 10
    tags: [core]
```

### Fields

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `content` | string | **Yes** | `""` | The text content. Supports YAML multiline strings (`|` for literal, `>` for folded). |

### Behavior

- Returns exactly **one chunk** containing the full `content` string
- The chunk's `source` and `title` are set to the source name
- Empty `content` returns zero chunks
- Token count is estimated at creation time

### When to Use

- System prompts that every agent receives
- Instructions, guidelines, or boilerplate
- Static configuration context (company info, rules)
- Any content that doesn't change between queries

### Example: Multiple Inline Sources with Priority

```yaml
sources:
  system_prompt:
    type: inline
    content: "You are a helpful assistant."
    priority: 10

  safety_notice:
    type: inline
    content: "Never share personal data. Always verify before acting."
    priority: 9

  response_format:
    type: inline
    content: "Format all responses in markdown with headers and bullet points."
    priority: 8
```

With `ranking: manual`, these will appear in priority order (highest first).

---

## `directory` -- Local Files

Reads files from a local directory with glob pattern matching, recursive traversal, and automatic markdown splitting.

### Config

```yaml
sources:
  knowledge_base:
    type: directory
    path: "./data/docs"
    patterns: ["**/*.md", "**/*.txt"]
    exclude_patterns: ["**/drafts/**", "**/archive/**"]
    recursive: true
    encoding: utf-8
    max_file_size: 1000000
    tags: [documentation]
```

### Fields

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `path` | string | **Yes** | `""` | Directory path. Relative paths resolve from the working directory. |
| `patterns` | list | No | `["**/*"]` | Glob patterns for files to include. Matched against relative paths. |
| `exclude_patterns` | list | No | `[]` | Glob patterns for files to exclude. |
| `recursive` | bool | No | `true` | Traverse subdirectories. |
| `encoding` | string | No | `"utf-8"` | File encoding. Undecodable files are skipped. |
| `max_file_size` | int | No | `1000000` | Max file size in bytes. Larger files are skipped. |

### Behavior

1. The directory is scanned (recursively if enabled)
2. Each file is matched against `patterns` (include) then `exclude_patterns` (exclude)
3. Files exceeding `max_file_size` are skipped
4. Each file is read with the configured encoding
5. **Markdown files** (`.md`, `.markdown`) are split by H2 headings -- each `## Section` becomes a separate chunk
6. **Other files** produce one chunk per file

### Markdown H2 Splitting

Markdown files are split at every `## ` heading. Each section becomes its own chunk:

```markdown
# My Document

Introduction text here.

## Installation

Install with pip install my-package.

## Configuration

Edit the config file at ~/.config/my-package.yaml.
```

This produces three chunks:

1. Title: filename, content: `"# My Document\n\nIntroduction text here."`
2. Title: `"Installation"`, content: `"## Installation\n\nInstall with pip install my-package."`
3. Title: `"Configuration"`, content: `"## Configuration\n\nEdit the config file..."`

This gives the relevance scorer fine-grained sections to rank, so the engine can return just the "Installation" section instead of the entire document.

If a markdown file has no H2 headings, it is returned as a single chunk (the filename becomes the title).

### Chunk Metadata

Each chunk includes:

| Key | Type | Description |
|-----|------|-------------|
| `mtime` | float | File modification timestamp (Unix epoch). Enables `recency` ranking. |

The chunk's `path` field is set to the relative path within the directory (e.g., `"guides/setup.md"`), which enables `deny_paths` filtering.

### Security

- **Path traversal protection**: every file path is resolved via `Path.resolve()` and verified to be inside the base directory. Symlink escapes are blocked.
- **File size limit**: `max_file_size` (default 1MB) prevents reading very large files.
- **Note**: the `path` config field can point to any directory the process has read access to. Restrict process permissions accordingly.

### Example: Multiple Directories with Different Patterns

```yaml
sources:
  markdown_docs:
    type: directory
    path: "./docs"
    patterns: ["**/*.md"]
    tags: [docs, markdown]

  config_examples:
    type: directory
    path: "./examples"
    patterns: ["**/*.yaml", "**/*.json"]
    max_file_size: 50000
    tags: [examples]

  code_snippets:
    type: directory
    path: "./src"
    patterns: ["**/*.py"]
    exclude_patterns: ["**/tests/**", "**/__pycache__/**"]
    tags: [code]
```

---

## `git_repo` -- Git Repository

Reads files from a git repository at a specific ref (branch, tag, or commit SHA). Uses `git ls-tree` and `git show` subprocess calls -- no working tree modifications, safe for production.

### Config

```yaml
sources:
  versioned_docs:
    type: git_repo
    path: "/repos/documentation"
    ref: "v2.1.0"
    patterns: ["docs/**/*.md", "README.md"]
    exclude_patterns: ["docs/internal/**"]
    tags: [documentation, versioned]
```

### Fields

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `path` | string | **Yes** | `""` | Path to the git repository root. |
| `ref` | string | No | `"HEAD"` | Git ref: branch name, tag, or commit SHA. |
| `patterns` | list | No | `["**/*"]` | Glob patterns for files to include. |
| `exclude_patterns` | list | No | `[]` | Glob patterns for files to exclude. |
| `max_file_size` | int | No | `1000000` | Max file size in bytes. |

### Behavior

1. `git ls-tree -r --name-only <ref>` lists all files at the specified ref
2. Files are filtered by `patterns` and `exclude_patterns`
3. `git show <ref>:<file>` reads each matching file's content
4. Markdown files are split by H2 headings (same as the directory source)
5. Files exceeding `max_file_size` are skipped

### Chunk Metadata

| Key | Type | Description |
|-----|------|-------------|
| `ref` | string | The git ref used to read the file. |

### Security

- **Ref validation**: git refs are validated against `^[a-zA-Z0-9._/-]+$` before any subprocess call. Refs containing `;`, `$`, `` ` ``, or other shell metacharacters are rejected.
- **Path validation**: file paths from `git ls-tree` are validated against a safe character set. Files with special characters in their names are skipped.
- **No shell=True**: all subprocess calls use list syntax.
- **Timeouts**: `git ls-tree` has a 30-second timeout, `git show` has a 10-second timeout.

### Requirements

- `git` must be available on the system PATH
- The path must be a valid git repository
- The ref must exist

### Use Cases

- **Versioned documentation:** Pin to a release tag (`ref: "v2.0.0"`) so context stays consistent with the deployed version
- **Branch-specific context:** Provide different context per branch (`ref: "feature/new-api"`)
- **Historical context:** Read from any commit to understand past state

### Example: Multiple Refs

```yaml
sources:
  stable_docs:
    type: git_repo
    path: "/repos/docs"
    ref: "v2.0.0"
    patterns: ["**/*.md"]
    tags: [stable]

  latest_docs:
    type: git_repo
    path: "/repos/docs"
    ref: "main"
    patterns: ["**/*.md"]
    tags: [latest]
```

---

## `http_api` -- REST API

Queries a REST API endpoint. Supports GET and POST, template substitution, custom headers, and JSON response parsing with dot-notation path navigation.

### Config

```yaml
sources:
  search_api:
    type: http_api
    url: "https://api.example.com/search?q={{query}}&limit=5"
    method: GET
    headers:
      Authorization: "Bearer ${API_TOKEN}"
      Accept: "application/json"
    response_path: "data.results"
    result_text_field: "content"
    result_title_field: "name"
    tags: [search, api]
```

### Fields

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `url` | string | **Yes** | `""` | API endpoint. `{{query}}` is replaced with the query text. |
| `method` | string | No | `"GET"` | HTTP method: `GET` or `POST`. |
| `headers` | dict | No | `{}` | HTTP headers. Values support `${ENV_VAR}` interpolation. |
| `body_template` | string | No | `""` | Request body for POST. `{{query}}` is replaced with the query text. |
| `response_path` | string | No | `""` | Dot-notation path to the results array in the JSON response. |
| `result_text_field` | string | No | `"text"` | Field name for chunk text in each result object. |
| `result_title_field` | string | No | `"title"` | Field name for chunk title in each result object. |

### Template Substitution

The `{{query}}` placeholder is replaced with the raw query text in both `url` and `body_template`:

```yaml
# GET with query in URL
url: "https://api.example.com/search?q={{query}}"

# POST with query in body
url: "https://api.example.com/search"
method: POST
body_template: '{"query": "{{query}}", "top_k": 10, "filters": {"active": true}}'
```

### Response Parsing

The engine parses JSON responses in three steps:

**Step 1: Navigate to results.** Use `response_path` to reach the array of results. For example, given this API response:

```json
{
  "status": "ok",
  "data": {
    "results": [
      {"content": "First result", "title": "Doc A"},
      {"content": "Second result", "title": "Doc B"}
    ]
  }
}
```

Set `response_path: "data.results"` to navigate to the results array.

**Step 2: Normalize.** If the navigated value is a dict, it is wrapped in a list. If it is a scalar, it becomes a single chunk. If it is already a list, it is used as-is.

**Step 3: Extract fields.** For each item in the list, `result_text_field` and `result_title_field` specify which keys to extract. Items that are plain strings (not dicts) are used directly as chunk content.

### Non-JSON Responses

If the response is not valid JSON, the entire response body is returned as a single chunk.

### Chunk Metadata

| Key | Type | Description |
|-----|------|-------------|
| `url` | string | The configured source URL (before template substitution). |

### Security

- **SSRF protection**: URLs are validated before every request. Private IPs (`127.0.0.1`, `10.x.x.x`, `172.16-31.x.x`, `192.168.x.x`), loopback, and link-local addresses are blocked. Only `http://` and `https://` schemes are allowed.
- **Validation after template substitution**: the URL is validated after `{{query}}` replacement, preventing query-based SSRF bypasses.
- **Timeout**: all requests have a 30-second timeout.

### Error Handling

- HTTP errors (4xx, 5xx) result in zero chunks (no exception propagated)
- Invalid URLs result in zero chunks
- Timeouts (30 seconds) result in zero chunks
- SSRF-blocked URLs result in zero chunks
- For POST requests, `Content-Type: application/json` is set automatically if not provided in `headers`

### Example: Vector Search API

```yaml
sources:
  vector_search:
    type: http_api
    url: "https://embeddings.internal.acme.com/search"
    method: POST
    headers:
      Authorization: "Bearer ${EMBEDDINGS_API_KEY}"
    body_template: |
      {
        "query": "{{query}}",
        "top_k": 10,
        "threshold": 0.7,
        "namespace": "production"
      }
    response_path: "matches"
    result_text_field: "text"
    result_title_field: "metadata.title"
    tags: [search, vectors]
```

---

## Writing a Custom Source

You can add custom source types by subclassing `Source` and registering with the `@register_source` decorator.

### Step 1: Implement the Source

```python
from theaios.context_router.sources import Source, register_source
from theaios.context_router.types import ContextChunk, Query, SourceConfig
from theaios.context_router.budget import estimate_tokens


@register_source("redis")
class RedisSource(Source):
    """Source that reads context from a Redis hash."""

    async def fetch(self, query: Query, config: SourceConfig) -> list[ContextChunk]:
        import redis.asyncio as redis

        # Use config.url for the Redis connection string
        client = redis.from_url(config.url)
        try:
            # Use config.path as the hash key
            data = await client.hgetall(config.path)
        finally:
            await client.aclose()

        chunks = []
        for key, value in data.items():
            text = value.decode("utf-8") if isinstance(value, bytes) else str(value)
            if not text.strip():
                continue

            chunks.append(ContextChunk(
                content=text,
                source=config.name,
                title=key.decode("utf-8") if isinstance(key, bytes) else str(key),
                token_count=estimate_tokens(text),
            ))

        return chunks
```

### Step 2: Register the Import

Make sure your module is imported before the `Router` is created. You can do this in your application's startup code:

```python
# Import to trigger @register_source decorator
import my_package.sources.redis_source  # noqa: F401

from theaios.context_router import Router, load_config

config = load_config("context-router.yaml")
router = Router(config)  # Now "redis" is available as a source type
```

### Step 3: Use in Config

```yaml
sources:
  session_context:
    type: redis
    url: "redis://localhost:6379/0"
    path: "agent:context:session-123"
    tags: [session, dynamic]
```

### Source Base Class

```python
class Source(ABC):
    @abstractmethod
    async def fetch(self, query: Query, config: SourceConfig) -> list[ContextChunk]:
        """Fetch context chunks from this source."""

    def fetch_sync(self, query: Query, config: SourceConfig) -> list[ContextChunk]:
        """Synchronous wrapper (uses asyncio.run internally)."""
```

Your `fetch()` method receives:

- `query` -- the incoming `Query` with `text`, `agent`, `tags`, and `metadata`
- `config` -- the `SourceConfig` parsed from YAML, with all common fields (`name`, `type`, `path`, `url`, `content`, `headers`, `patterns`, etc.)

Return a list of `ContextChunk` objects. Each chunk should have:

- `content` -- the text content (required for relevance scoring)
- `source` -- set to `config.name`
- `title` -- a human-readable title
- `token_count` -- use `estimate_tokens(text)` from the budget module
- `path` -- set if applicable (enables `deny_paths` filtering)
- `metadata` -- any source-specific metadata

### Guidelines

- **Handle errors gracefully.** If your source is unavailable, return an empty list rather than raising an exception. The engine silently skips failed sources.
- **Use `asyncio.to_thread()` for blocking I/O.** If your source uses a synchronous library, wrap the call in `asyncio.to_thread()` to avoid blocking the event loop.
- **Set `token_count` on chunks.** Use `estimate_tokens()` from the budget module so the budget trimmer doesn't need to re-estimate.
- **Set `path` for file-based sources.** This enables the `deny_paths` permission feature.

### Registry Functions

```python
from theaios.context_router.sources import register_source, get_source, list_sources

# Register a source class
@register_source("my_source")
class MySource(Source): ...

# Get an instance by name
source = get_source("my_source")

# List all registered source types
names = list_sources()  # ["directory", "git_repo", "http_api", "inline", "my_source"]
```
