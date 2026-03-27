# Generate Configs with AI

You can use any LLM (Claude, ChatGPT, Gemini, etc.) to generate context-router configurations that are fully compatible with this library. Copy-paste one of the prompts below, describe your setup, and get a production-ready YAML file.

---

## Prompt 1: Full Config from Scratch

Use this when starting from zero. The AI will ask about your agents and data sources, then generate a complete config.

````
I need you to generate a context-router YAML configuration file for the theaios-context-router library. This config will control how AI agents discover and receive context.

Before generating, ask me about:
1. What does my company/product do?
2. What AI agents do we have or plan to deploy? (names, roles)
3. What data sources do we have? (documentation directories, git repos, APIs, static content)
4. What are our access control requirements? (which agents can see what)
5. What is our target LLM context window size?
6. Do we need caching?

Then generate a YAML file following this exact specification:

```yaml
version: "1.0"                    # Always "1.0"
metadata:
  name: string                    # Config name
  description: string             # What this config governs
  author: string                  # Config owner

variables:                        # Shared values referenced as $var_name in routes
  key: value                      # Can be strings, numbers, booleans, or lists

sources:                          # Where context lives (keyed by name)
  source_name:
    type: inline                  # Source type: inline | directory | git_repo | http_api
    # --- inline fields ---
    content: string               # Static text content (required for inline)
    # --- directory fields ---
    path: string                  # Directory path (required for directory)
    patterns: ["**/*.md"]         # Glob patterns to include (default: ["**/*"])
    exclude_patterns: ["**/x/**"] # Glob patterns to exclude (default: [])
    recursive: true               # Traverse subdirectories (default: true)
    encoding: utf-8               # File encoding (default: utf-8)
    max_file_size: 1000000        # Max file size in bytes (default: 1000000)
    # --- git_repo fields ---
    path: string                  # Repo path (required for git_repo)
    ref: "HEAD"                   # Git ref: branch, tag, or commit (default: HEAD)
    patterns: ["**/*.md"]         # Glob patterns to include
    exclude_patterns: []          # Glob patterns to exclude
    # --- http_api fields ---
    url: string                   # API URL, use {{query}} for query text (required for http_api)
    method: GET                   # HTTP method: GET or POST (default: GET)
    headers:                      # HTTP headers (support ${ENV_VAR} interpolation)
      Authorization: "Bearer ${API_TOKEN}"
    body_template: string         # POST body, use {{query}} for query text
    response_path: string         # Dot-notation path to results in JSON response
    result_text_field: "text"     # Field name for chunk text (default: text)
    result_title_field: "title"   # Field name for chunk title (default: title)
    # --- common fields ---
    enabled: true                 # Enable/disable (default: true)
    description: string           # Human description
    tags: [tag1, tag2]            # Labels for filtering
    priority: 0                   # Priority (higher = higher priority, default: 0)

routes:                           # Which sources to consult for which queries
  - name: unique-route-name       # Required: unique identifier
    when: "expression"            # Condition — see expression syntax below
    sources: [source1, source2]   # Required: source names to consult
    description: string           # Human description
    enabled: true                 # Enable/disable (default: true)
    tags: [tag1]                  # Labels

permissions:                      # Per-agent access control
  - agent: "*"                    # Agent name or "*" for wildcard
    allow_sources: [src1]         # Explicitly allowed sources
    deny_sources: [src2]          # Explicitly denied sources (deny wins over allow)
    deny_paths: ["**/secret/**"]  # Glob patterns for denied file paths
    default: allow                # Default when source not in either list: allow | deny

budget:
  max_tokens: 8000                # Max tokens for assembled context (default: 8000)
  ranking: relevance              # Ranking strategy: relevance | recency | manual (default: relevance)
  truncation: drop                # Truncation: drop | truncate_end | truncate_middle (default: drop)
  estimator: chars_div4           # Token estimator: chars_div4 | words | whitespace (default: chars_div4)
  reserve_tokens: 0               # Tokens to reserve for other prompt content (default: 0)

cache:
  enabled: false                  # Enable disk cache (default: false)
  directory: ".context-router-cache"  # Cache directory (default: .context-router-cache)
  ttl: 300                        # Time-to-live in seconds (default: 300)
  max_entries: 1000               # Max cache entries (default: 1000)

# Expression syntax for "when" clauses:
# Primary field:     text (the query text)
# Other fields:      agent, tags, and any query.metadata keys
# Comparisons:       ==, !=, >, <, >=, <=
# String ops:        contains, starts_with, ends_with
# Membership:        in, not in (with lists or variables)
# Boolean:           and, or, not
# Variables:         $variable_name (references the variables section)
# Literals:          "string", 123, true, false, null, ["list"]
# Grouping:          parentheses ()
# Examples:
#   'text contains "policy"'
#   'agent == "hr-bot"'
#   'agent in $engineering_teams'
#   '(text contains "deploy" or text contains "release") and agent in $eng_teams'
#   '' (empty = always matches, useful for default routes)
```

Important rules for generation:
- Every route must have a unique name and at least one source
- Every source must have a valid type and its required fields
- Always include a default route with `when: ""` that provides baseline context
- Use variables for values that might change (team lists, API hosts)
- Use environment variable interpolation `${ENV_VAR}` for secrets in headers
- Use `{{query}}` in http_api urls and body_templates for query substitution
- Use tags on sources for organization
- Add clear descriptions to sources and routes
- Set appropriate budget based on the target LLM context window
- Enable cache for http_api sources to reduce latency
````

---

## Prompt 2: Add Sources and Routes to an Existing Config

Use this when you already have a config and want to extend it.

````
I have an existing theaios-context-router configuration. I need to add new sources and routes for [DESCRIBE YOUR NEED].

Here is my current config:

```yaml
[PASTE YOUR CURRENT YAML HERE]
```

Generate additional sources and routes following the same format. For each new addition:
- Source names must not conflict with existing sources
- Route names must be unique (no duplicates with existing routes)
- Routes must reference defined sources (existing or newly added)
- Use the expression syntax for when clauses: text contains "keyword", agent == "name", field in $variable, and/or/not, parentheses for grouping
- Match the style and conventions of the existing config

Also suggest any new variables, permission rules, or budget adjustments needed.
````

---

## Prompt 3: Config for a Specific Use Case

Use this to generate a config tailored to a specific deployment scenario.

````
Generate a complete theaios-context-router YAML config for this use case:

Scenario: [e.g., "Customer support agents with access to help docs and a ticket API"]

Details:
- Agents: [e.g., "support-bot (tier 1), escalation-bot (tier 2), admin-bot"]
- Data sources: [e.g., "help center markdown files in ./docs, Zendesk API for tickets, inline system prompt"]
- Access rules: [e.g., "tier 1 only sees public docs, tier 2 sees internal docs too, admin sees everything"]
- Target LLM: [e.g., "Claude with 200K context window" or "GPT-4 with 8K context"]

Generate a production-ready YAML config using this format:
- version: "1.0"
- Source types: inline (content field), directory (path + patterns), git_repo (path + ref + patterns), http_api (url + method + headers + body_template + response_path)
- Route conditions use expression syntax: text contains "keyword", agent == "name", field in $variable_list, and/or/not, empty string for always-match
- Permissions: agent-specific allow/deny_sources, deny_paths globs, default allow or deny
- Budget: max_tokens, ranking (relevance/recency/manual), truncation (drop/truncate_end/truncate_middle)
- Cache: enabled for API sources, ttl based on data freshness needs
- Use ${ENV_VAR} for secrets in headers
- Use {{query}} in API URLs and body templates
- Include clear descriptions and tags on everything
````

---

## Prompt 4: Convert Informal Rules to Config

Use this when you have requirements in plain English and want to formalize them.

````
I need to convert these context routing requirements into a theaios-context-router YAML config:

[PASTE YOUR REQUIREMENTS — examples:]
- "The engineering assistant should see API docs, runbooks, and code examples"
- "The HR bot should only see HR policies and the employee handbook"
- "All agents get a system prompt reminding them to be concise"
- "When someone asks about deployments, include the runbooks"
- "The intern bot should not see any confidential files"
- "API search results should be cached for 5 minutes"

Convert each requirement into the YAML format:

Sources: inline (static content), directory (local files with glob patterns), git_repo (git files at a ref), http_api (REST API with {{query}} template substitution)

Routes: name + when condition (expression syntax: text contains "x", agent == "y", $variable references, and/or/not, empty = always match) + source list

Permissions: per-agent allow_sources, deny_sources, deny_paths (glob patterns), default (allow/deny)

Budget: max_tokens, ranking (relevance/recency/manual), truncation (drop/truncate_end/truncate_middle), reserve_tokens

Explain any ambiguous requirements and suggest how to interpret them.
````

---

## Prompt 5: Security Review a Config

Use this to audit an existing config for gaps.

````
Review this theaios-context-router configuration for security and correctness:

```yaml
[PASTE YOUR YAML HERE]
```

Check for:
1. **Missing default route** — is there a route with `when: ""` for baseline context?
2. **Overly broad permissions** — are any agents getting access to sources they shouldn't?
3. **Missing deny_paths** — should any agents have file-level restrictions (e.g., **/secrets/**, **/credentials/**)?
4. **Permission default** — is the default set correctly? Should it be "deny" instead of "allow"?
5. **Unused sources** — are any sources defined but not referenced by any route?
6. **Route expression errors** — are the when clauses syntactically valid? (operators: ==, !=, >, <, contains, starts_with, ends_with, in, not in, and, or, not; primary field is "text")
7. **Budget configuration** — is max_tokens appropriate for the target LLM? Is reserve_tokens set if a system prompt is injected separately?
8. **Cache settings** — should caching be enabled for API sources? Is the TTL appropriate?
9. **Secret exposure** — are API tokens using ${ENV_VAR} interpolation instead of being hardcoded?
10. **Missing descriptions/tags** — do all sources and routes have descriptions and tags for maintainability?

For each issue found, provide the exact YAML fix.
````

---

## Tips for Better Results

1. **Be specific about your data sources.** "Markdown files in ./docs/engineering with patterns **/*.md" produces better configs than "some documentation."

2. **Name your agents.** "hr-bot, eng-assistant, exec-assistant" tells the AI exactly what permission rules to create.

3. **Mention your LLM.** "Claude with 200K context" vs. "GPT-3.5 with 4K context" leads to very different budget settings.

4. **Describe your API responses.** "The search API returns `{"results": [{"content": "...", "title": "..."}]}`" helps the AI set the right `response_path` and field names.

5. **Iterate.** Generate a first draft, validate with `context-router validate`, then ask the AI to fix any issues.

---

## Validate AI-Generated Configs

Always validate before using in production:

```bash
# Check syntax and structure
context-router validate --config generated-config.yaml

# Inspect the full configuration
context-router inspect --config generated-config.yaml

# Test a query
context-router query --config generated-config.yaml \
  --text "What is the remote work policy?" \
  --agent "hr-bot"

# Test permissions — check denied_sources
context-router query --config generated-config.yaml \
  --text "Show me salary data" \
  --agent "intern-bot" \
  --output json

# Test with different agents to verify access control
for agent in hr-bot eng-assistant intern-bot; do
  echo "=== $agent ==="
  context-router query --config generated-config.yaml \
    --text "test query" --agent "$agent" --output json
done
```
