# Configuration Reference

A context-router configuration is a single YAML file that defines your sources, routing rules, permissions, and budget. It is the source of truth for how your AI agents receive context.

This page is the complete reference. Read it once, then use it as a lookup.

---

## File Structure

Every config file has these top-level sections:

```yaml
version: "1.0"              # Required. Always "1.0" for now.
metadata:                    # Optional. Who wrote this, when, why.
variables:                   # Optional. Shared values used in route expressions.
sources:                     # Required. Where context lives.
routes:                      # Required. Which sources to consult for which queries.
permissions:                 # Optional. Per-agent access control.
budget:                      # Optional. Token budget and ranking configuration.
cache:                       # Optional. Disk cache settings.
```

Only `version` and at least one source + one route are required. Everything else has sensible defaults.

---

## Version

```yaml
version: "1.0"
```

Always `"1.0"` for the current release. The engine rejects unknown versions.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `version` | string | **Yes** | Config format version. Must be `"1.0"`. |

---

## Metadata

```yaml
metadata:
  name: acme-corp-context-router
  description: Context routing for ACME's AI agents
  author: engineering@acme.com
```

Metadata is for humans and tooling. The engine doesn't use it for routing -- it stores it for `context-router inspect` output and audit purposes.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `name` | string | `""` | Router configuration name. Shows in `context-router inspect`. |
| `description` | string | `""` | What this configuration governs. |
| `author` | string | `""` | Who owns this configuration. |

---

## Variables

Variables are shared values that route expressions reference with `$variable_name`. They keep your routes DRY and make it easy to update a value in one place.

```yaml
variables:
  company_name: "ACME Corp"
  engineering_teams: ["platform", "backend", "frontend", "data"]
  max_context_priority: 10
```

Use variables in `when` clauses:

```yaml
routes:
  - name: engineering-docs
    when: "agent in $engineering_teams"
    sources: [eng_docs, api_docs]
```

Variables can be strings, numbers, booleans, or lists. They are substituted at evaluation time, not at parse time -- so they work correctly with all operators including `in`.

```yaml
# This works: checks if agent is in the list
when: "agent in $engineering_teams"
```

---

## Sources

Sources define where context lives. Each source has a name, a type, and type-specific configuration fields.

```yaml
sources:
  system_prompt:
    type: inline
    content: "You are a helpful engineering assistant."
    priority: 10

  docs:
    type: directory
    path: "./docs"
    patterns: ["**/*.md"]
    exclude_patterns: ["**/drafts/**"]
    tags: [documentation]
```

### Common Source Fields

These fields apply to all source types:

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `type` | string | **(required)** | Source type: `inline`, `directory`, `git_repo`, or `http_api`. |
| `enabled` | bool | `true` | Set to `false` to disable without removing. |
| `description` | string | `""` | Human-readable description of this source. |
| `tags` | list | `[]` | Labels for filtering with `context-router inspect --tag`. |
| `priority` | int | `0` | Priority value. Higher priority sources are fetched first. Used by manual ranking. |

### Source Type: `inline`

Static content embedded directly in the config. Returns a single chunk.

```yaml
sources:
  system_prompt:
    type: inline
    content: |
      You are a helpful assistant for ACME Corp.
      Be concise and accurate. Cite your sources.
    priority: 10
```

| Field | Type | Default | Required | Description |
|-------|------|---------|----------|-------------|
| `content` | string | `""` | **Yes** | The text content to return. Supports YAML multiline strings. |

### Source Type: `directory`

Reads files from a local directory. Supports glob patterns, recursive traversal, file size limits, encoding configuration, and automatic markdown H2 splitting.

```yaml
sources:
  knowledge_base:
    type: directory
    path: "./data/knowledge"
    patterns: ["**/*.md", "**/*.txt"]
    exclude_patterns: ["**/archive/**", "**/.git/**"]
    recursive: true
    encoding: utf-8
    max_file_size: 1000000
```

| Field | Type | Default | Required | Description |
|-------|------|---------|----------|-------------|
| `path` | string | `""` | **Yes** | Path to the directory. Relative paths are resolved from the working directory. |
| `patterns` | list | `["**/*"]` | No | Glob patterns for files to include. Matched against relative paths within the directory. |
| `exclude_patterns` | list | `[]` | No | Glob patterns for files to exclude. Checked after include patterns. |
| `recursive` | bool | `true` | No | Whether to traverse subdirectories. |
| `encoding` | string | `"utf-8"` | No | File encoding. Files that fail to decode are skipped. |
| `max_file_size` | int | `1000000` | No | Maximum file size in bytes. Files exceeding this are skipped. |

**Markdown splitting:** Files with `.md` or `.markdown` extensions are automatically split by H2 headings (`## `). Each section becomes a separate chunk with the heading text as its title. Files without H2 headings are returned as a single chunk.

**Metadata:** Each chunk from a directory source includes `metadata.mtime` (file modification timestamp as a float), which enables `recency` ranking.

### Source Type: `git_repo`

Reads files from a git repository at a specific ref (branch, tag, or commit). Uses `git ls-tree` to enumerate files and `git show` to read content. No working tree modifications -- safe for production use.

```yaml
sources:
  versioned_docs:
    type: git_repo
    path: "/path/to/repo"
    ref: "main"
    patterns: ["docs/**/*.md"]
    exclude_patterns: ["docs/drafts/**"]
    max_file_size: 500000
```

| Field | Type | Default | Required | Description |
|-------|------|---------|----------|-------------|
| `path` | string | `""` | **Yes** | Path to the git repository root. |
| `ref` | string | `"HEAD"` | No | Git ref to read from: branch name, tag, or commit SHA. |
| `patterns` | list | `["**/*"]` | No | Glob patterns for files to include. |
| `exclude_patterns` | list | `[]` | No | Glob patterns for files to exclude. |
| `max_file_size` | int | `1000000` | No | Maximum file size in bytes (estimated from content length). |

**Markdown splitting:** Same H2-based splitting as the directory source.

**Metadata:** Each chunk includes `metadata.ref` (the git ref used).

**Requirements:** `git` must be available on the system PATH. Operations time out after 30 seconds (ls-tree) or 10 seconds (show per file).

### Source Type: `http_api`

Queries a REST API endpoint. Supports GET and POST methods, template substitution for the query text, custom headers, and JSON response parsing with dot-notation path navigation.

```yaml
sources:
  search_api:
    type: http_api
    url: "https://api.example.com/search?q={{query}}"
    method: GET
    headers:
      Authorization: "Bearer ${API_TOKEN}"
      Accept: "application/json"
    response_path: "results"
    result_text_field: "content"
    result_title_field: "title"

  vector_search:
    type: http_api
    url: "https://api.example.com/embeddings/search"
    method: POST
    headers:
      Authorization: "Bearer ${API_TOKEN}"
    body_template: '{"query": "{{query}}", "top_k": 5}'
    response_path: "matches"
    result_text_field: "text"
    result_title_field: "title"
```

| Field | Type | Default | Required | Description |
|-------|------|---------|----------|-------------|
| `url` | string | `""` | **Yes** | API endpoint URL. `{{query}}` is replaced with the query text. |
| `method` | string | `"GET"` | No | HTTP method: `GET` or `POST`. |
| `headers` | dict | `{}` | No | HTTP headers. Values support `${ENV_VAR}` interpolation. |
| `body_template` | string | `""` | No | Request body for POST requests. `{{query}}` is replaced with the query text. |
| `response_path` | string | `""` | No | Dot-notation path to navigate the JSON response to the results array. Empty means the root. |
| `result_text_field` | string | `"text"` | No | Field name in each result object containing the text content. |
| `result_title_field` | string | `"title"` | No | Field name in each result object containing the title. |

**Template substitution:** The `{{query}}` placeholder in `url` and `body_template` is replaced with the raw query text at request time.

**Response parsing:**

1. The JSON response is navigated using `response_path` (e.g., `"results"` navigates to `data["results"]`, `"data.items"` navigates to `data["data"]["items"]`)
2. The result is normalized to a list (a single dict becomes `[dict]`)
3. Each item's `result_text_field` and `result_title_field` are extracted as chunk content and title
4. Non-JSON responses are returned as a single chunk

**Metadata:** Each chunk includes `metadata.url` (the source URL).

**Timeouts:** HTTP requests time out after 30 seconds.

---

## Routes

Routes map query conditions to sources. They answer: "For this query, which sources should we consult?"

```yaml
routes:
  - name: default
    when: ""
    sources: [system_prompt, docs]
    description: "Always include system prompt and general docs"

  - name: policy-questions
    when: 'text contains "policy" or text contains "compliance"'
    sources: [compliance_docs]
    description: "Add compliance docs for policy-related queries"
    tags: [compliance]

  - name: engineering
    when: 'agent == "eng-assistant"'
    sources: [api_docs, code_examples]
    tags: [engineering]
```

### Route Fields

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `name` | string | **Yes** | -- | Unique identifier. Shows in `response.matched_routes` and `context-router inspect`. |
| `sources` | list | **Yes** | -- | Source names to consult when this route matches. Must reference defined sources. |
| `when` | string | No | `""` | Condition expression. Empty = always matches. See [Expression Language](expressions.md). |
| `description` | string | No | `""` | Human-readable description. |
| `enabled` | bool | No | `true` | Set to `false` to disable without deleting. |
| `tags` | list | No | `[]` | Labels for filtering and reporting. |

### How Routes Are Evaluated

1. Routes are evaluated **top-to-bottom** in declaration order
2. **All matching routes contribute sources** -- this is not first-match-wins
3. Source lists from matching routes are **merged and deduplicated**
4. An empty `when` clause (`""`) **always matches**
5. Disabled routes (`enabled: false`) are **skipped entirely**

This means you can have a catch-all default route plus specialized routes that add extra sources for specific query types.

### The `when` Clause

The `when` clause uses a safe expression language to evaluate conditions against the query. The primary field for most conditions is `text` (the query text).

Available context fields:

| Field | Source | Example |
|-------|--------|---------|
| `text` | `query.text` | `text contains "policy"` |
| `agent` | `query.agent` | `agent == "hr-bot"` |
| `tags` | `query.tags` | `"onboarding" in tags` |
| Any key | `query.metadata` | `department == "engineering"` |
| `$variable` | `config.variables` | `agent in $allowed_agents` |

See the [Expression Language](expressions.md) page for the full syntax reference.

---

## Permissions

Permissions control which agents can access which sources. They are evaluated after route matching -- even if a route matches, the agent might not have access to all of the route's sources.

```yaml
permissions:
  - agent: "*"
    default: allow

  - agent: "intern-bot"
    allow_sources: [public_docs]
    deny_sources: [internal_docs, financial_data]
    deny_paths: ["**/confidential/**"]
    default: deny

  - agent: "eng-assistant"
    deny_sources: [hr_docs]
    deny_paths: ["**/salaries/**"]
```

### Permission Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `agent` | string | `"*"` | Agent identifier to match. `"*"` matches all agents. |
| `allow_sources` | list | `[]` | Sources this agent is explicitly allowed to access. |
| `deny_sources` | list | `[]` | Sources this agent is explicitly denied from accessing. **Deny takes precedence over allow.** |
| `deny_paths` | list | `[]` | Glob patterns for file paths to exclude from results. Applied after fetching. |
| `default` | string | `"allow"` | Default permission when a source is not in either list: `"allow"` or `"deny"`. |

### How Permissions Are Resolved

1. Permission rules are evaluated in order
2. Rules matching the exact agent name **and** wildcard rules (`"*"`) are **merged**
3. `deny_sources` lists are unioned
4. `allow_sources` lists are unioned
5. `deny_paths` lists are concatenated
6. The most restrictive `default` wins (`"deny"` beats `"allow"`)
7. If no rules match the agent, the default is `"allow"`

For each source, the decision logic is:

1. If the source is in `deny_sources` -> **denied**
2. If the source is in `allow_sources` -> **allowed**
3. Otherwise -> use the `default` setting

See [Permissions](permissions.md) for detailed examples and patterns.

---

## Budget

The budget section controls token limits, ranking strategy, and truncation behavior.

```yaml
budget:
  max_tokens: 8000
  ranking: relevance
  truncation: drop
  estimator: chars_div4
  reserve_tokens: 500
```

### Budget Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `max_tokens` | int | `8000` | Maximum total tokens for the assembled context. Must be >= 1. |
| `ranking` | string | `"relevance"` | How to rank chunks before budget trimming: `"relevance"`, `"recency"`, or `"manual"`. |
| `truncation` | string | `"drop"` | What to do when a chunk exceeds the remaining budget: `"drop"`, `"truncate_end"`, or `"truncate_middle"`. |
| `estimator` | string | `"chars_div4"` | Token estimation method: `"chars_div4"`, `"words"`, or `"whitespace"`. |
| `reserve_tokens` | int | `0` | Tokens to reserve (subtracted from `max_tokens`). Useful for system prompts injected separately. Must be >= 0. |

### Ranking Strategies

| Value | Sort key | Description |
|-------|----------|-------------|
| `relevance` | `relevance_score` descending | Chunks most relevant to the query appear first. **Default.** |
| `recency` | `metadata.mtime` descending | Most recently modified files appear first. Best for "what changed" queries. |
| `manual` | Insertion order | Preserves the order sources are declared. Best when source `priority` controls ordering. |

### Truncation Strategies

| Value | Behavior | When to use |
|-------|----------|-------------|
| `drop` | Skip the chunk entirely | Safe default. No partial content that might confuse the LLM. |
| `truncate_end` | Cut from the end, append `[...]` | When the beginning of a document is most important. |
| `truncate_middle` | Keep start and end, insert `[...truncated...]` in the middle | When both the beginning (introduction) and end (conclusion) matter. |

### Token Estimators

| Value | Method | Accuracy |
|-------|--------|----------|
| `chars_div4` | `ceil(len(text) / 4)` | Good approximation for GPT-like tokenizers. **Default.** |
| `words` | `len(text.split())` | Rougher estimate, faster. |
| `whitespace` | `len(text.split())` | Same as `words` (whitespace-based splitting). |

See [Budget Management](budget.md) for tuning guidance.

---

## Cache

The cache section enables disk-based caching of source fetch results.

```yaml
cache:
  enabled: true
  directory: ".context-router-cache"
  ttl: 300
  max_entries: 1000
```

### Cache Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `enabled` | bool | `false` | Enable disk caching. When false, every query fetches fresh data. |
| `directory` | string | `".context-router-cache"` | Directory for cache files. Created automatically if it doesn't exist. |
| `ttl` | int | `300` | Time-to-live in seconds. Entries older than this are evicted on read. Must be >= 0. |
| `max_entries` | int | `1000` | Maximum number of cached entries. Oldest entries are evicted when the limit is reached. Must be >= 1. |

Cache is keyed by `(source_name, query_text)` -- the SHA-256 hash of these two values. Each source's results are cached independently.

---

## Environment Variable Interpolation

All string values in the config support `${ENV_VAR}` interpolation:

```yaml
sources:
  api:
    type: http_api
    url: "https://${API_HOST}/search"
    headers:
      Authorization: "Bearer ${API_TOKEN}"
```

If the environment variable is not set, the placeholder is left as-is (no error, no expansion). Interpolation is applied recursively to all string values before parsing.

---

## Complete Enterprise Example

A production-ready config for a multi-agent enterprise system:

```yaml
version: "1.0"
metadata:
  name: acme-corp-context-router
  description: Context routing for ACME Corp's AI agent fleet
  author: engineering@acme.com

variables:
  company_name: "ACME Corp"
  engineering_teams: ["platform", "backend", "frontend", "data", "infra"]
  sensitive_departments: ["finance", "legal", "hr"]

sources:
  # --- Static context ---
  system_prompt:
    type: inline
    content: |
      You are an AI assistant for ACME Corp.
      Be helpful, concise, and always cite your sources.
      Do not share confidential information outside of authorized contexts.
    priority: 10
    tags: [core]

  agent_instructions:
    type: inline
    content: |
      When answering questions:
      1. Start with the most relevant information
      2. Include links to source documents when available
      3. Flag if the information might be outdated
    priority: 9
    tags: [core]

  # --- Documentation ---
  public_docs:
    type: directory
    path: "./docs/public"
    patterns: ["**/*.md", "**/*.txt"]
    exclude_patterns: ["**/drafts/**"]
    description: Public-facing documentation
    tags: [documentation, public]

  internal_docs:
    type: directory
    path: "./docs/internal"
    patterns: ["**/*.md"]
    exclude_patterns: ["**/archived/**"]
    max_file_size: 500000
    description: Internal engineering documentation
    tags: [documentation, internal]

  hr_handbook:
    type: directory
    path: "./docs/hr"
    patterns: ["**/*.md", "**/*.pdf"]
    description: HR policies and employee handbook
    tags: [hr, compliance]

  # --- Git-versioned content ---
  api_reference:
    type: git_repo
    path: "/repos/api-docs"
    ref: "main"
    patterns: ["docs/**/*.md", "openapi/**/*.yaml"]
    description: API reference from the docs repo
    tags: [engineering, api]

  runbooks:
    type: git_repo
    path: "/repos/runbooks"
    ref: "main"
    patterns: ["**/*.md"]
    exclude_patterns: ["**/deprecated/**"]
    description: Operational runbooks
    tags: [engineering, ops]

  # --- External APIs ---
  knowledge_search:
    type: http_api
    url: "https://search.internal.acme.com/api/v1/search?q={{query}}&limit=5"
    method: GET
    headers:
      Authorization: "Bearer ${SEARCH_API_TOKEN}"
    response_path: "results"
    result_text_field: "content"
    result_title_field: "title"
    description: Internal knowledge base search
    tags: [search, knowledge]

  confluence_api:
    type: http_api
    url: "https://acme.atlassian.net/wiki/rest/api/search"
    method: POST
    headers:
      Authorization: "Bearer ${CONFLUENCE_TOKEN}"
      Content-Type: "application/json"
    body_template: '{"cql": "text ~ \"{{query}}\"", "limit": 5}'
    response_path: "results"
    result_text_field: "content.body.view.value"
    result_title_field: "content.title"
    description: Confluence wiki search
    tags: [search, wiki]

routes:
  # Default route: always provide system context
  - name: always
    when: ""
    sources: [system_prompt, agent_instructions]
    description: "System prompt and instructions for every query"
    tags: [core]

  # General documentation
  - name: general-docs
    when: ""
    sources: [public_docs]
    description: "Public docs available for all queries"
    tags: [documentation]

  # Policy and HR questions
  - name: hr-questions
    when: 'text contains "policy" or text contains "handbook" or text contains "pto" or text contains "benefits" or text contains "onboarding"'
    sources: [hr_handbook]
    description: "HR handbook for policy-related queries"
    tags: [hr]

  # Engineering queries
  - name: engineering
    when: 'agent in $engineering_teams or text contains "api" or text contains "deploy" or text contains "architecture"'
    sources: [internal_docs, api_reference, runbooks]
    description: "Engineering docs for technical queries"
    tags: [engineering]

  # Search augmentation for complex queries
  - name: knowledge-search
    when: 'text contains "how" or text contains "why" or text contains "explain" or text contains "troubleshoot"'
    sources: [knowledge_search, confluence_api]
    description: "Search APIs for complex questions"
    tags: [search]

permissions:
  # Default: all agents can access public sources
  - agent: "*"
    allow_sources: [system_prompt, agent_instructions, public_docs]
    default: deny

  # Engineering agents: broad access, deny HR
  - agent: "eng-assistant"
    allow_sources: [internal_docs, api_reference, runbooks, knowledge_search, confluence_api]
    deny_sources: [hr_handbook]
    deny_paths: ["**/salaries/**", "**/compensation/**"]
    default: deny

  # HR agent: HR access, deny engineering internals
  - agent: "hr-bot"
    allow_sources: [hr_handbook, public_docs, knowledge_search]
    deny_sources: [internal_docs, api_reference, runbooks]
    deny_paths: ["**/security/**", "**/credentials/**"]
    default: deny

  # Executive agent: broad read access
  - agent: "exec-assistant"
    allow_sources: [public_docs, internal_docs, hr_handbook, knowledge_search, confluence_api]
    deny_paths: ["**/credentials/**", "**/secrets/**"]
    default: allow

budget:
  max_tokens: 8000
  ranking: relevance
  truncation: truncate_end
  estimator: chars_div4
  reserve_tokens: 500

cache:
  enabled: true
  directory: ".context-router-cache"
  ttl: 300
  max_entries: 2000
```

---

## Validation

Always validate your config before deploying:

```bash
context-router validate --config context-router.yaml
# Config is valid: 9 sources, 5 routes, 4 permissions
```

The validator checks:

- Version is supported (`"1.0"`)
- Every source has a valid `type` and its required fields
- Every route has a unique `name` and references defined sources
- Permission rules reference defined sources
- Budget values are within valid ranges
- Cache values are within valid ranges

If validation fails, the error output includes the specific field and reason:

```
Validation failed:
  - sources.api: http_api source requires 'url'
  - routes[2] (engineering): source 'api_docs' is not defined
  - budget.ranking: invalid value 'custom', expected one of ['manual', 'recency', 'relevance']
```

---

## Tips for Writing Good Configs

**Start small.** Begin with 2-3 sources and a default route. Add complexity as you learn what your agents actually need.

**Use the default route pattern.** Have one route with `when: ""` that provides baseline context (system prompt, core docs). Add specialized routes on top.

**Name sources clearly.** The source name shows up in chunk metadata and CLI output. `internal_docs` is better than `source_3`.

**Use tags for organization.** Tags let you filter sources in `context-router inspect --tag engineering` and understand your config at a glance.

**Use variables for values that change.** Team lists, API hosts, department names -- put them in `variables` so config updates don't require editing every route.

**Set appropriate budgets.** 4000 tokens for simple assistants, 8000-16000 for complex agents. Always set `reserve_tokens` if you inject a system prompt separately.

**Enable cache for API sources.** HTTP API sources benefit most from caching. Directory sources are already fast. Set TTL based on how often your data changes.

**Version in git.** The YAML file is the config. Treat it like code: pull requests, reviews, blame history.
