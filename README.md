<div align="center">
  <a href="https://cohorte-ai.github.io/context-router/">
    <picture>
      <source media="(prefers-color-scheme: dark)" srcset=".github/images/TheAIOS-ContextRouter-darkmode.svg">
      <source media="(prefers-color-scheme: light)" srcset=".github/images/TheAIOS-ContextRouter.svg">
      <img alt="theaios-context-router" src=".github/images/TheAIOS-ContextRouter.svg" width="60%">
    </picture>
  </a>
</div>

<div align="center">
  <h3>Intelligent context routing for AI agents — YAML configs, multi-source retrieval, any platform.</h3>
</div>

<div align="center">
  <a href="https://opensource.org/licenses/Apache-2.0" target="_blank"><img src="https://img.shields.io/badge/license-Apache%202.0-blue" alt="License"></a>
  <a href="https://pypi.org/project/theaios-context-router/" target="_blank"><img src="https://img.shields.io/pypi/v/theaios-context-router" alt="PyPI"></a>
  <a href="https://cohorte-ai.github.io/context-router/" target="_blank"><img src="https://img.shields.io/badge/docs-mkdocs-blue" alt="Docs"></a>
  <a href="https://x.com/CohorteAI" target="_blank"><img src="https://img.shields.io/twitter/follow/CohorteAI?style=social" alt="Follow @CohorteAI"></a>
</div>

<br>

> [!NOTE]
> Part of the [theaios](https://github.com/Cohorte-ai) ecosystem. Install with `pip install theaios-context-router`.

## What It Does

Define how AI agents discover and receive context in YAML. The engine routes each query to the right sources, enforces agent permissions, fetches content in parallel, scores relevance, and trims to a token budget. No manual prompt-stuffing. Deterministic, fast, auditable.

- **YAML configuration** — declare sources, routes, permissions, and budgets in a single file
- **Multi-source retrieval** — inline content, local directories, git repos, REST APIs
- **Expression-based routing** — route queries to sources using a safe expression language (`text contains "policy"`, boolean logic, variables)
- **Agent permissions** — per-agent allow/deny lists for sources and file paths
- **Token budget management** — relevance ranking, configurable truncation strategies (drop, truncate_end, truncate_middle)
- **Automatic markdown splitting** — splits `.md` files by H2 headings for fine-grained retrieval
- **Disk cache with TTL** — cache source results to avoid redundant fetches
- **Extensible sources** — add custom sources via `@register_source` plugin system
- **CLI tools** — validate configs, inspect routers, run queries from the terminal

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
```

**Queries** tell the engine what context to find. Each query has a `text` (what to search for), an `agent` (who is asking), and optional `tags` and `metadata`:

```python
# Basic query
router.query(Query(text="How do expenses work?"))

# Agent-specific query (permissions apply)
router.query(Query(text="Show me project docs", agent="eng-assistant"))

# Query with metadata (accessible in route expressions)
router.query(Query(
    text="Find onboarding guide",
    agent="hr-bot",
    tags=["onboarding"],
    metadata={"department": "engineering"},
))
```

The engine evaluates route conditions against the query, filters by permissions, fetches from allowed sources in parallel, scores relevance, and trims to the token budget. The `ContextResponse` contains the ranked chunks, metadata, and timing information.

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
context-router query --config context-router.yaml --text "expenses" --output json
context-router cache stats --config context-router.yaml
context-router cache clear --config context-router.yaml
```

## Why This Library?

Every AI agent needs context. The options today:

| Approach | Problem |
|----------|---------|
| **Manual prompt-stuffing** | Hardcoded, doesn't scale, no permissions |
| **RAG frameworks** (LlamaIndex, LangChain) | Heavy dependencies, vector DB required, complex setup |
| **Vendor context windows** (Gemini, Claude) | Locked to one provider, no access control |
| **Build your own** | Weeks of engineering, no standard format |

theaios-context-router is **lightweight** (pure Python, no vector DB), **declarative** (YAML configs that teams can review), **permission-aware** (per-agent access control), and **deterministic** (same query = same context, every time).

## Source Types

| Source | Description | Config Key |
|--------|-------------|------------|
| **inline** | Static content embedded in config | `content` |
| **directory** | Read files from a local directory | `path`, `patterns` |
| **git_repo** | Read files from a git ref | `path`, `ref`, `patterns` |
| **http_api** | Query a REST API endpoint | `url`, `method`, `body_template` |

Custom sources: implement the `Source` base class and register with `@register_source("my_source")`.

## Generate Configs with AI

Don't want to write YAML by hand? Use any LLM to generate a config. Copy-paste one of our [ready-made prompts](https://cohorte-ai.github.io/context-router/ai-config-generator/) and get a production-ready YAML file in seconds. Prompts are included for:

- Generating a full config from scratch (the AI asks about your sources and agents)
- Extending an existing config with new sources or routes
- Converting plain-English routing rules to YAML
- Security-auditing an existing config for permission gaps

Then validate: `context-router validate --config generated-config.yaml`

## Documentation

Full documentation at **[cohorte-ai.github.io/context-router](https://cohorte-ai.github.io/context-router/)** — including the [configuration reference](https://cohorte-ai.github.io/context-router/config-syntax/), [source types](https://cohorte-ai.github.io/context-router/sources/), [expression language](https://cohorte-ai.github.io/context-router/expressions/), [permissions](https://cohorte-ai.github.io/context-router/permissions/), and [budget management](https://cohorte-ai.github.io/context-router/budget/).

## Part of the theaios Ecosystem

theaios-context-router is one of the [theaios](https://github.com/Cohorte-ai) platform components. It works standalone or alongside:

- [theaios-guardrails](https://github.com/Cohorte-ai/guardrails) — declarative guardrails for AI agent governance
- [theaios-trustgate](https://github.com/Cohorte-ai/trustgate) — formal AI reliability certification

## License

Apache 2.0 — see [LICENSE](LICENSE).
