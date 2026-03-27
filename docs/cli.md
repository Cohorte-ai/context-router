# CLI Reference

The `context-router` CLI lets you validate configs, inspect routers, run queries, and manage the cache from the terminal.

---

## Commands

### `context-router version`

Show the installed version.

```bash
context-router version
# context-router 0.1.0
```

---

### `context-router validate`

Check a configuration file for errors without running the engine. Validates structure, types, field values, and cross-references (e.g., routes referencing undefined sources).

```bash
context-router validate --config context-router.yaml
# Config is valid: 5 sources, 3 routes, 2 permissions
```

| Option | Short | Default | Description |
|--------|-------|---------|-------------|
| `--config` | `-c` | `context-router.yaml` | Config file path |

**Exit codes:**

| Code | Meaning |
|------|---------|
| 0 | Config is valid |
| 1 | Config has errors |

**Error output example:**

```bash
context-router validate --config broken.yaml
# Validation failed:
#   - sources.api: http_api source requires 'url'
#   - routes[2] (engineering): source 'api_docs' is not defined
#   - budget.ranking: invalid value 'custom', expected one of ['manual', 'recency', 'relevance']
```

The validator checks:

- Version is `"1.0"`
- Every source has a valid `type` and its required fields (`content` for inline, `path` for directory/git_repo, `url` for http_api)
- Every route has a unique `name` and references defined sources
- Every route has at least one source
- Permission `allow_sources` and `deny_sources` reference defined sources
- Permission `default` is `"allow"` or `"deny"`
- `budget.max_tokens` >= 1
- `budget.ranking` is one of `relevance`, `recency`, `manual`
- `budget.truncation` is one of `drop`, `truncate_end`, `truncate_middle`
- `budget.estimator` is one of `chars_div4`, `words`, `whitespace`
- `budget.reserve_tokens` >= 0
- `cache.ttl` >= 0
- `cache.max_entries` >= 1

---

### `context-router inspect`

Display a formatted summary of the router configuration: sources, routes, permissions, and budget settings.

```bash
context-router inspect --config context-router.yaml
```

| Option | Short | Default | Description |
|--------|-------|---------|-------------|
| `--config` | `-c` | `context-router.yaml` | Config file path |
| `--tag` | | -- | Filter sources by tag |

**Filter by tag:**

```bash
context-router inspect --config context-router.yaml --tag engineering
```

This shows only sources tagged with `engineering`, along with all routes and permissions.

**Exit codes:**

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Config file not found or invalid |

---

### `context-router query`

Execute a context query against the router. This runs the full pipeline: route matching, permission filtering, parallel fetch, relevance scoring, ranking, and budget trimming.

```bash
# Console output (default)
context-router query --config context-router.yaml --text "What is the remote work policy?"

# JSON output
context-router query --config context-router.yaml --text "expenses" --output json

# Agent-specific query
context-router query --config context-router.yaml --text "deploy the API" --agent eng-assistant

# Export to file
context-router query --config context-router.yaml --text "PTO policy" --output json --output-file result.json
```

| Option | Short | Default | Description |
|--------|-------|---------|-------------|
| `--config` | `-c` | `context-router.yaml` | Config file path |
| `--text` | `-t` | **(required)** | Query text |
| `--agent` | `-a` | `"default"` | Agent identifier |
| `--output` | `-o` | `console` | Output format: `console` or `json` |
| `--output-file` | | -- | Write JSON output to file (implies JSON format) |

**Console output** shows a human-readable summary: matched routes, chunk titles and sources, token counts, and timing.

**JSON output** includes the full response structure: all chunks with content, source, title, path, relevance score, token count, and metadata. Also includes `total_tokens`, `was_truncated`, `matched_routes`, `denied_sources`, and `evaluation_time_ms`.

**Exit codes:**

| Code | Meaning |
|------|---------|
| 0 | Query executed successfully (even if no results) |
| 1 | Config file not found or invalid |

---

### `context-router cache stats`

Show cache statistics: entry count, total size, TTL, and max entries.

```bash
context-router cache stats --config context-router.yaml
# Cache: enabled
# Directory: .context-router-cache
# Entries: 42
# Total Size: 156832 bytes
# TTL: 300s
# Max Entries: 1000
```

| Option | Short | Default | Description |
|--------|-------|---------|-------------|
| `--config` | `-c` | `context-router.yaml` | Config file path |

If the cache is disabled in the config, the output shows `Cache: disabled` with zero entries.

**Exit codes:**

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Config file not found or invalid |

---

### `context-router cache clear`

Clear cache entries. Optionally clear only entries for a specific source.

```bash
# Clear all cache entries
context-router cache clear --config context-router.yaml
# Cleared 42 cache entries

# Clear entries for a specific source
context-router cache clear --config context-router.yaml --source docs
# Cleared 7 cache entries
```

| Option | Short | Default | Description |
|--------|-------|---------|-------------|
| `--config` | `-c` | `context-router.yaml` | Config file path |
| `--source` | `-s` | -- | Only clear entries for this source name |

**Exit codes:**

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Config file not found or invalid |

---

## Command Tree

```
context-router
  |-- version            Show version
  |-- validate           Validate a config file
  |-- inspect            Display router summary
  |-- query              Execute a context query
  |-- cache
       |-- stats         Show cache statistics
       |-- clear         Clear cache entries
```

---

## Common Workflows

### Validate before deploying

```bash
context-router validate --config production-router.yaml && echo "Ready to deploy"
```

### Test a query as a specific agent

```bash
context-router query \
  --config context-router.yaml \
  --text "Show me salary data" \
  --agent "intern-bot" \
  --output json | python -m json.tool
```

Check the `denied_sources` field to see if permissions blocked any sources.

### Debug routing

```bash
# See which routes match
context-router query --config context-router.yaml --text "How do deployments work?"
# Look at "matched_routes" in the output

# Compare two queries
context-router query -c context-router.yaml -t "deployment guide" -o json > query1.json
context-router query -c context-router.yaml -t "PTO policy" -o json > query2.json
```

### Cache management

```bash
# Check cache state
context-router cache stats -c context-router.yaml

# Clear stale data for a specific source after updating its content
context-router cache clear -c context-router.yaml --source knowledge_base

# Full cache reset
context-router cache clear -c context-router.yaml
```

---

## Global Behavior

- All commands read the config file using `load_config()`, which performs full validation including environment variable interpolation (`${ENV_VAR}`)
- If the config file is not found, commands print an error to stderr and exit with code 1
- If the config file has validation errors, all errors are listed to stderr and the command exits with code 1
