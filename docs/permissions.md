# Permissions

Permissions control which agents can access which context sources. They provide a security boundary between route matching ("this query needs these sources") and actual data access ("this agent is allowed to see these sources").

---

## How Permissions Work

The permission system operates at two levels:

1. **Source-level filtering** -- which sources an agent can access (checked before fetching)
2. **Path-level filtering** -- which file paths an agent can see (checked after fetching)

```
Route matching: "Query needs sources A, B, C"
    |
    v
Permission check: "Agent X can access A and B, denied C"
    |
    v
Fetch from A and B only
    |
    v
Path filtering: "Remove chunks from B matching **/secrets/**"
    |
    v
Final chunks from A and (filtered) B
```

Denied sources are recorded in `response.denied_sources` for auditability -- you can always see what was blocked and why.

---

## Config Syntax

```yaml
permissions:
  - agent: "*"
    default: allow

  - agent: "intern-bot"
    allow_sources: [public_docs]
    deny_sources: [internal_docs, financial_data]
    deny_paths: ["**/confidential/**", "**/secrets/**"]
    default: deny

  - agent: "eng-assistant"
    allow_sources: [internal_docs, api_reference, runbooks]
    deny_sources: [hr_docs]
    deny_paths: ["**/salaries/**"]
```

### Permission Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `agent` | string | `"*"` | Agent identifier to match. `"*"` is a wildcard that matches all agents. |
| `allow_sources` | list | `[]` | Sources this agent is explicitly allowed to access. |
| `deny_sources` | list | `[]` | Sources this agent is explicitly denied. **Deny always takes precedence.** |
| `deny_paths` | list | `[]` | Glob patterns for file paths to exclude from this agent's results. |
| `default` | string | `"allow"` | Default permission when a source is in neither list: `"allow"` or `"deny"`. |

---

## Resolution Logic

When a query arrives, the engine resolves the effective permission for the requesting agent by merging all matching permission rules.

### Step 1: Match Rules

Permission rules are evaluated in order. A rule matches if:

- `agent` is `"*"` (wildcard -- matches every agent), **or**
- `agent` exactly equals the query's agent name

Both exact-match and wildcard rules can match the same agent. All matching rules contribute to the resolved permission.

### Step 2: Merge

Matching rules are merged:

- `deny_sources` lists are **unioned** (all denied sources from all matching rules)
- `allow_sources` lists are **unioned** (all allowed sources from all matching rules)
- `deny_paths` lists are **concatenated** (all path patterns from all matching rules)
- `default` uses the **most restrictive** value: if any matching rule has `default: deny`, the resolved default is `deny`

### Step 3: Decide Per Source

For each source that the route matching stage identified:

1. If the source is in `deny_sources` -> **denied** (explicit deny always wins)
2. If the source is in `allow_sources` -> **allowed**
3. Otherwise -> use the resolved `default` setting

### Step 4: Path Filtering (Post-Fetch)

After chunks are fetched from allowed sources, each chunk's `path` field is checked against `deny_paths` patterns. Chunks matching any pattern are removed.

Path patterns use `fnmatch` glob syntax:

| Pattern | Matches |
|---------|---------|
| `**/secrets/**` | Any file inside a `secrets/` directory at any depth |
| `*.env` | Files ending in `.env` in the root |
| `config/credentials.*` | Any credentials file in the config directory |
| `**/internal/*.md` | Markdown files in any `internal/` directory |

Chunks without a `path` field (e.g., from `inline` or `http_api` sources) are never filtered by path.

---

## No Rules = Allow All

If no permission rules are defined, or if no rules match the current agent, the default behavior is **allow all sources**. Permissions are opt-in restrictions on top of your routing.

```yaml
# No permissions section — all agents see all matched sources
sources:
  docs:
    type: directory
    path: "./docs"

routes:
  - name: default
    when: ""
    sources: [docs]

# No permissions: every agent can access 'docs'
```

---

## Common Patterns

### Pattern 1: Default Deny with Explicit Allow

The most secure approach. Start by denying everything, then explicitly allow what each agent needs.

```yaml
permissions:
  # Deny everything by default
  - agent: "*"
    default: deny

  # HR bot: only HR docs
  - agent: "hr-bot"
    allow_sources: [hr_handbook, public_docs]

  # Engineering bot: engineering sources
  - agent: "eng-assistant"
    allow_sources: [internal_docs, api_reference, code_examples]

  # Exec bot: broad read access
  - agent: "exec-assistant"
    allow_sources: [public_docs, internal_docs, hr_handbook, financial_reports]
```

With this pattern, a new agent added to the system sees nothing until explicitly granted access.

### Pattern 2: Default Allow with Selective Deny

The simpler approach. Allow everything, then block specific sensitive sources.

```yaml
permissions:
  # Allow everything by default
  - agent: "*"
    default: allow

  # Block sensitive sources from general agents
  - agent: "general-assistant"
    deny_sources: [financial_data, hr_records, security_logs]

  # Block everything sensitive from the intern bot
  - agent: "intern-bot"
    deny_sources: [internal_docs, financial_data, hr_records, security_logs]
    deny_paths: ["**/confidential/**"]
```

### Pattern 3: Path-Level Access Control

When an agent needs access to a source but not all files within it.

```yaml
permissions:
  - agent: "eng-assistant"
    allow_sources: [internal_docs]
    deny_paths:
      - "**/salaries/**"
      - "**/compensation/**"
      - "**/performance-reviews/**"
      - "**/credentials/**"
      - "**/.env"
```

This lets the engineering assistant see all internal docs except sensitive HR and security files.

### Pattern 4: Layered Permissions

Combine a wildcard baseline with agent-specific overrides.

```yaml
permissions:
  # Baseline: everyone gets public docs, deny by default for everything else
  - agent: "*"
    allow_sources: [system_prompt, public_docs]
    default: deny

  # Engineering team: add internal sources
  - agent: "eng-assistant"
    allow_sources: [internal_docs, api_reference, runbooks]
    deny_paths: ["**/secrets/**"]

  # The wildcard rule and the eng-assistant rule BOTH match.
  # Result: allow_sources = {system_prompt, public_docs, internal_docs, api_reference, runbooks}
  # deny_paths = ["**/secrets/**"]
  # default = deny (most restrictive wins)
```

---

## Interactions with Routing

Permissions and routes are two separate layers:

| | Routes | Permissions |
|---|--------|-------------|
| **What they control** | Which sources are relevant to a query | Which sources an agent can access |
| **Evaluated** | First | Second (after route matching) |
| **Scope** | Query content and metadata | Agent identity |
| **Override** | Routes add sources | Permissions restrict access |

A source must pass **both** gates to be fetched:

1. A matching route must include the source
2. The agent's permissions must allow the source

If a route includes sources A, B, and C, but the agent only has permission for A and B, only A and B are fetched. Source C appears in `response.denied_sources`.

---

## Inspecting Permissions

Use the CLI to see how permissions are configured:

```bash
context-router inspect --config context-router.yaml
```

This shows all sources, routes, and permission rules in a formatted summary.

To test what a specific agent can access, run a query:

```bash
context-router query --config context-router.yaml \
  --text "test query" \
  --agent "intern-bot" \
  --output json
```

The JSON output includes `denied_sources` -- the list of sources that were blocked by permissions.

---

## Validation

The config validator checks that all sources referenced in `allow_sources` and `deny_sources` are actually defined:

```bash
context-router validate --config context-router.yaml
```

If you reference an undefined source, you will see:

```
Validation failed:
  - permissions[1]: allow_sources reference 'nonexistent_source' is not defined
```

The validator also checks that `default` is either `"allow"` or `"deny"`.
