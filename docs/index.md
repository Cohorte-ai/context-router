# theaios-context-router

**Intelligent context routing for AI agents -- YAML configs, multi-source retrieval, any platform.**

theaios-context-router is a context retrieval engine that lets you define how AI agents discover and receive context in YAML. Write routing rules that teams can review, version them in git, and assemble precisely the right context for every query -- deterministic, fast, auditable.

## Why YAML?

Because context management is a shared concern. The person defining "which docs this agent should see" is rarely the person writing the agent code. YAML bridges that gap:

- **Product teams** can define which sources each agent accesses
- **Engineers** integrate with two lines of code
- **Security teams** can review and audit permissions in git
- **Nobody** needs to learn a new programming language

## What It Does

```
Agent query (text, agent identity, metadata)
    |
    v
Engine evaluates routes (~0.1ms)
    |
    v
Permission filtering (agent allow/deny)
    |
    v
Parallel fetch from matched sources
    |
    v
Relevance scoring + ranking + budget trimming
    |
    v
ContextResponse: ranked chunks, token counts, timing
```

Every query is routed deterministically. Same config + same query = same context, every time.

## Quick Start

```bash
pip install theaios-context-router
```

**1. Write a config:**

```yaml
# context-router.yaml
version: "1.0"

sources:
  system_prompt:
    type: inline
    content: "You are a helpful assistant. Be concise."
    priority: 10

  docs:
    type: directory
    path: "./data"
    patterns: ["**/*.md", "**/*.txt"]

routes:
  - name: default
    when: ""
    sources: [system_prompt, docs]

  - name: policy-questions
    when: 'text contains "policy"'
    sources: [docs]

budget:
  max_tokens: 4000
  ranking: relevance
  truncation: drop
```

**2. Use it:**

```python
from theaios.context_router import Router, load_config, Query

config = load_config("context-router.yaml")
router = Router(config)

response = router.query(Query(text="What is the remote work policy?"))

print(response.matched_routes)  # ["policy-questions", "default"]
print(len(response.chunks))     # 3
print(response.total_tokens)    # 847
print(response.text)            # All chunks concatenated
```

**Or one-liner:**

```python
from theaios.context_router import query

response = query("context-router.yaml", text="What is the PTO policy?")
```

**3. CLI:**

```bash
context-router validate --config context-router.yaml
context-router inspect --config context-router.yaml
context-router query --config context-router.yaml --text "What is the remote work policy?"
context-router cache stats --config context-router.yaml
```

## Documentation

| Page | What you'll learn |
|------|-------------------|
| [Concepts](concepts.md) | How the engine works -- the 8-stage pipeline, caching, performance characteristics |
| [Configuration Reference](config-syntax.md) | The complete YAML config reference -- every section, every field, every source type |
| [Expression Language](expressions.md) | The `when` clause syntax -- operators, fields, variables, grammar |
| [Source Types](sources.md) | Built-in sources (inline, directory, git_repo, http_api) and how to write custom sources |
| [Permissions](permissions.md) | Per-agent source access control, deny_paths, default allow/deny |
| [Budget Management](budget.md) | Token estimation, relevance scoring, ranking strategies, truncation |
| [CLI Reference](cli.md) | `context-router validate`, `inspect`, `query`, `cache stats`, `cache clear` |
| [Python API](api-reference.md) | `Router`, `load_config`, `query`, all types, source registry |
| [Generate Configs with AI](ai-config-generator.md) | Copy-paste prompts for any LLM to generate valid YAML configs |
| [Security](security.md) | SSRF protection, command injection prevention, path traversal defense, atomic writes |

## Part of the theaios Ecosystem

theaios-context-router is one of the [theaios](https://github.com/Cohorte-ai) platform components. It works standalone or alongside:

- [theaios-guardrails](https://github.com/Cohorte-ai/guardrails) -- declarative guardrails for AI agent governance
- [theaios-trustgate](https://github.com/Cohorte-ai/trustgate) -- formal AI reliability certification
