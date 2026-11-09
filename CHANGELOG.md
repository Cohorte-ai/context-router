# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.4] - 2026-11-09

### Fixed

- A route whose `when` used an undefined `$variable` (a typo) or `matches` (the context router has no matchers) loaded fine and then never matched, silently. Such configs are now rejected when they load (`load_config`, `Router(...)`, the CLI), with a "did you mean" suggestion. Disabled routes are not checked. **If your config stops loading after upgrading, it had a route that never matched.**
- The docs described `matches` as resolving named matchers in the router; it never did. Corrected.

- Mistakes in a config's structure no longer load silently: unknown keys (`enabeld: false` left a route on; a misspelled top-level section was dropped), sections of the wrong type (`routes` written as a mapping loaded zero routes), and values of the wrong type (`when: 42` matched every query; `enabled: "false"` in quotes left the route on). They are rejected with a suggestion where one exists.
- `Router(...)` built from a `RouterConfig` in code now runs the same validation as `load_config` and raises `ConfigError`.
- YAML syntax errors, a directory or a non-UTF-8 file passed as the config raise `ConfigError` with the file and line instead of a Python traceback.
- String values that spell numbers compare as numbers in route conditions (theaios-core 0.1.1).
- Docs: the validator lists and the variables section now match the behavior.
- **Security:** `deny_paths: ["**/secrets/**"]` did not hide a `secrets/` folder at the top of a source, so an agent denied those files still received them. In path patterns, `**/` now also matches zero folders. This applies to `deny_paths`, `patterns` and `exclude_patterns`: the default `patterns: ["**/*"]` now includes top-level files (it skipped them), and `docs/**/*.md` includes files directly in `docs/`.
- **Security:** query `metadata` could override the query's own fields in route conditions: `metadata={"agent": "hr-bot"}` sent by an intern matched `agent == "hr-bot"`. `text`, `agent` and `tags` now always win; metadata keys stay reachable at the top level and, as `metadata.key`, also in the documented nested form.
- `context-router inspect` and `query` printed text in square brackets as terminal markup (names, conditions and chunk content could disappear); all text is now shown verbatim.
- `examples/permissions_example.py` said an unknown agent is "denied by default" while it received every source; it now adds the catch-all `agent: "*"` deny rule that produces that result.
- Custom source types registered with `@register_source` are accepted by validation (they were rejected unless built in code, and the new in-code validation briefly rejected those too).
- `matched_routes` in the README quick start is in declaration order.

### Changed

- Requires theaios-core 0.1.1 or later.

## [0.2.3] - 2026-11-09

### Changed

- The expression engine and `${VAR}` interpolation now come from [theaios-core](https://github.com/Cohorte-ai/theaios-core), a new dependency shared by the theaios libraries. The four libraries carried identical copies of the engine; it now lives in one place. Existing configs, imports (`theaios.context_router.expressions` still works) are unchanged.

### Fixed

- Expressions longer than 10,000 characters or nested deeper than 64 levels now raise `ExpressionError` instead of crashing with a Python `RecursionError`. Long `and` / `or` chains no longer hit the recursion limit.

## [0.2.2] - 2026-09-10

### Added

- `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `SECURITY.md`

### Changed

- CI toolchain pinned to verified versions (ruff 0.15.x, mypy 1.19.x, pytest <10)

## [0.2.1] - 2026-03-29

### Security

- **CRITICAL**: git_repo source — validate git refs and file paths against whitelist regex to prevent command injection
- **CRITICAL**: directory source — defense-in-depth path traversal check (resolve + startswith base)
- **CRITICAL**: http_api source — SSRF protection blocks private IPs, loopback, link-local, non-HTTP schemes
- **HIGH**: cache — atomic writes via tempfile + rename to prevent corruption
- **HIGH**: config — structural validation before env var interpolation to prevent secret leakage
- **MEDIUM**: cache — JSON structure validation on load (type checks, skip malformed entries)

### Added

- Security documentation page (docs/security.md)
- Security section in README with protection summary table
- Security notes in source type docs (directory, git_repo, http_api)

## [0.2.0] - 2026-03-28

### Added

- Optional embedding-based relevance scoring (`ranking: embedding`)
- `EmbeddingConfig` dataclass for embedding model/API configuration
- `EmbeddingScorer` class with disk-cached document embeddings and batch scoring
- New optional dependency group: `pip install theaios-context-router[embeddings]` (numpy + openai)
- Benchmarks: 4-way comparison (keyword vs TF-IDF vs embeddings vs LLM judge)
- Benchmarks: routing accuracy, permission enforcement (100%), budget efficiency

### Changed

- `VALID_RANKINGS` now includes `"embedding"` as a valid ranking strategy
- Budget docs updated with embedding section, performance comparison table

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
