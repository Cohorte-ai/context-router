# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-03-27

### Added

- **Core engine** — full context routing pipeline: route matching, permission filtering, parallel source fetching, relevance scoring, ranking, budget trimming, and response assembly.
- **YAML configuration** — declarative config format (`context-router.yaml`) with validation, environment variable interpolation (`${VAR}`), and typed parsing into `RouterConfig`.
- **Expression language** — safe, sandboxed expression parser and evaluator for route conditions. Supports field access, dot-notation, string/number/boolean literals, comparisons (`==`, `!=`, `>`, `<`, `>=`, `<=`), pattern operators (`contains`, `starts_with`, `ends_with`, `matches`), boolean logic (`and`, `or`, `not`), list membership (`in`, `not in`), and variable substitution (`$var`).
- **Source types:**
  - `inline` — static content embedded directly in the config.
  - `directory` — reads files from a local directory with glob pattern matching, exclude patterns, recursive traversal, file size limits, and automatic markdown H2 splitting.
  - `git_repo` — reads files from a git repository at a specific ref using `git ls-tree` and `git show`.
  - `http_api` — queries REST API endpoints with GET/POST methods, body template substitution (`{{query}}`), JSON response path navigation, and configurable result field extraction.
- **Source registry** — plugin system with `@register_source` decorator for custom source types.
- **Permission system** — per-agent permission rules with allow/deny source lists, deny path patterns (glob matching), wildcard agent matching, rule merging, and most-restrictive-default-wins semantics.
- **Token budget management** — token estimation (chars_div4, words, whitespace), keyword-overlap relevance scoring with stopword filtering, ranking strategies (relevance, recency, manual), and truncation strategies (drop, truncate_end, truncate_middle) with reserve token support.
- **Disk cache** — JSON-file-based cache with TTL expiry, per-source invalidation, max entry enforcement, and cache statistics.
- **CLI** (`context-router`) — commands for `version`, `validate`, `inspect`, `query` (console and JSON output), `cache stats`, and `cache clear`.
- **Reporting** — console-formatted query results and JSON export.
- **Async support** — async source fetching with `asyncio.gather` for parallel retrieval, sync wrapper for non-async callers.
- **One-liner API** — `theaios.context_router.query()` for quick prototyping.

### Dependencies

- `pyyaml>=6.0` — YAML parsing
- `click>=8.0` — CLI framework
- `rich>=13.0` — console output formatting
- `httpx>=0.27` — async HTTP client for API sources
- `aiofiles>=24.0` — async file I/O

[0.1.0]: https://github.com/Cohorte-ai/context-router/releases/tag/v0.1.0
