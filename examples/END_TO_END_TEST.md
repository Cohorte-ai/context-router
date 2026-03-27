# theaios-context-router — End-to-End Test Guide

Test every feature from a fresh install. No API keys needed for local sources.

**Requirements:** Python 3.10+
**Estimated time:** ~10 minutes
**Cost:** $0 (local sources only; HTTP API source requires a real endpoint)

---

## Setup

### macOS / Linux

```bash
mkdir context-router-test && cd context-router-test
python3 -m venv .venv
source .venv/bin/activate
pip install theaios-context-router
```

### Windows (PowerShell)

```powershell
mkdir context-router-test; cd context-router-test
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install theaios-context-router
```

---

## Generate test data

### Create sample documents

### macOS / Linux

```bash
mkdir -p data/policies data/projects

cat > data/policies/remote-work.md << 'EOF'
# Remote Work Policy

## Eligibility

All full-time employees who have completed their probationary period (90 days) are eligible
for remote work. Contractors and part-time employees may request remote work on a case-by-case basis.

## Communication

Remote employees must be available during core hours (10 AM - 3 PM in their local timezone).
All team meetings should be attended via video call.

## Equipment

The company provides a laptop and monitor for remote workers. Employees are responsible for
maintaining a reliable internet connection with a minimum speed of 25 Mbps download.
EOF

cat > data/policies/expenses.md << 'EOF'
# Expense Policy

## Travel Expenses

Employees may book economy-class flights for domestic travel. Business class is permitted for
international flights exceeding 6 hours. Hotel accommodation should not exceed $200 per night.

## Reimbursement Process

Expense reports must be submitted within 30 days of the expense. Reimbursements are processed
bi-weekly on the 1st and 15th of each month.
EOF

cat > data/projects/atlas.md << 'EOF'
# Project Atlas

## Overview

Project Atlas is the company's next-generation data platform initiative. The goal is to
consolidate all data pipelines into a unified lakehouse architecture.

## Team

- **Lead**: Sarah Chen (Principal Engineer)
- **Backend**: 4 engineers
- **Data Engineering**: 3 engineers

## Milestones

| Milestone | Target Date | Status |
|-----------|-------------|--------|
| Architecture Review | 2026-02-15 | Complete |
| Ingestion MVP | 2026-04-01 | In Progress |
EOF
```

### Create a config file

```bash
cat > context-router.yaml << 'EOF'
version: "1.0"
metadata:
  name: test-router
  description: Test context router

sources:
  system_prompt:
    type: inline
    content: |
      You are a helpful company assistant. Answer questions based on the provided context.
      Be concise and cite specific policies when relevant.

  company_docs:
    type: directory
    path: "./data"
    patterns: ["**/*.md"]
    recursive: true

routes:
  - name: policy-questions
    when: 'text contains "policy" or text contains "expense" or text contains "remote" or text contains "travel"'
    sources: [system_prompt, company_docs]

  - name: project-questions
    when: 'text contains "project" or text contains "atlas" or text contains "milestone"'
    sources: [system_prompt, company_docs]

  - name: default
    sources: [system_prompt, company_docs]

permissions:
  - agent: "*"
    default: allow

  - agent: external-bot
    allow_sources: [system_prompt]
    deny_sources: [company_docs]
    default: deny

budget:
  max_tokens: 4000
  ranking: relevance
  truncation: drop
  estimator: chars_div4
EOF
```

### Windows alternative: Python script

```powershell
python -c "
import pathlib, textwrap
for d in ['data/policies', 'data/projects']:
    pathlib.Path(d).mkdir(parents=True, exist_ok=True)
pathlib.Path('data/policies/remote-work.md').write_text('# Remote Work Policy\n\n## Eligibility\n\nAll full-time employees are eligible.\n\n## Communication\n\nCore hours: 10 AM - 3 PM.\n')
pathlib.Path('data/policies/expenses.md').write_text('# Expense Policy\n\n## Travel\n\nEconomy flights for domestic travel.\n\n## Reimbursement\n\nSubmit within 30 days.\n')
pathlib.Path('data/projects/atlas.md').write_text('# Project Atlas\n\n## Overview\n\nNext-gen data platform.\n\n## Team\n\nLead: Sarah Chen.\n')
print('Created sample documents')
# Then create context-router.yaml manually from the README
"
```

---

# Part 1: CLI

## 1. Version & Help

```bash
context-router version
context-router --help
```

Expected: version `0.1.0`, commands listed (`validate`, `inspect`, `query`, `cache`, `version`).

---

## 2. Validate Config

```bash
context-router validate --config context-router.yaml
```

Expected: `Config is valid: 3 sources, 3 routes, 2 permissions`

---

## 3. Inspect Config

```bash
context-router inspect --config context-router.yaml
```

Expected: formatted tables showing sources (with type, priority), routes (with conditions), permissions (per agent), budget settings, and cache status.

---

## 4. Query — Policy Question (Route Match)

```bash
context-router query --config context-router.yaml --text "What is the remote work policy?"
```

Expected: multiple chunks returned from `company_docs` (remote-work.md sections) + system_prompt. Route `policy-questions` matched.

---

## 5. Query — Project Question (Different Route)

```bash
context-router query --config context-router.yaml --text "What is project atlas?"
```

Expected: chunks from atlas.md. Route `project-questions` matched.

---

## 6. Query — Default Route (No Specific Match)

```bash
context-router query --config context-router.yaml --text "Tell me about the company"
```

Expected: chunks from all sources. Route `default` matched.

---

## 7. Query — JSON Output

```bash
context-router query --config context-router.yaml --text "What is the expense policy?" --output json
```

Expected: structured JSON with chunks, total_tokens, matched_routes, evaluation_time_ms.

---

## 8. Query — Restricted Agent (Permission Denied)

```bash
context-router query --config context-router.yaml --text "Tell me everything" --agent external-bot
```

Expected: only the system_prompt chunk returned. `company_docs` denied by permission.

---

## 9. Cache Commands

```bash
context-router cache stats --config context-router.yaml
context-router cache clear --config context-router.yaml
```

Expected: cache stats (entries, size) and clear confirmation. (Cache is disabled by default in our test config — enable it to test.)

---

# Part 2: Python API

## 10. Load and Query

```python
from theaios.context_router import Router, load_config, Query

config = load_config("context-router.yaml")
router = Router(config)

response = router.query(Query(text="What is the remote work policy?"))
print(f"Chunks: {len(response.chunks)}")
print(f"Tokens: {response.total_tokens}")
print(f"Routes: {response.matched_routes}")
print(f"Time: {response.evaluation_time_ms:.1f}ms")
```

---

## 11. One-Liner Query

```python
from theaios.context_router import query

response = query("context-router.yaml", text="What is project atlas?")
print(f"Chunks: {len(response.chunks)}, Tokens: {response.total_tokens}")
```

---

## 12. Iterate Over Chunks

```python
from theaios.context_router import Router, load_config, Query

router = Router(load_config("context-router.yaml"))
response = router.query(Query(text="expense reimbursement"))

for chunk in response.chunks:
    print(f"[{chunk.source}] {chunk.title}")
    print(f"  Tokens: {chunk.token_count}, Score: {chunk.relevance_score:.2f}")
    print(f"  Path: {chunk.path or 'N/A'}")
    print(f"  Content: {chunk.content[:100]}...")
    print()
```

---

## 13. Permission Filtering

```python
from theaios.context_router import Router, load_config, Query

router = Router(load_config("context-router.yaml"))

# Full access
r1 = router.query(Query(text="Tell me everything", agent="default"))
print(f"default:      {len(r1.chunks)} chunks, denied: {r1.denied_sources}")

# Restricted
r2 = router.query(Query(text="Tell me everything", agent="external-bot"))
print(f"external-bot: {len(r2.chunks)} chunks, denied: {r2.denied_sources}")
```

---

## 14. Assemble Context for LLM

```python
from theaios.context_router import Router, load_config, Query

router = Router(load_config("context-router.yaml"))
response = router.query(Query(text="What is the remote work policy?"))

# The assembled context — ready to inject into an LLM prompt
context_for_llm = "\n\n---\n\n".join(
    f"## [{c.source}] {c.title}\n{c.content}" for c in response.chunks
)
print(f"Context length: {len(context_for_llm)} chars, {response.total_tokens} tokens")
print(f"First 500 chars:\n{context_for_llm[:500]}")
```

---

## 15. Source Registry

```python
from theaios.context_router import list_sources

print(f"Available sources: {list_sources()}")
# Expected: ['directory', 'git_repo', 'http_api', 'inline']
```

---

## 16. Custom Source

```python
from theaios.context_router import Router, Query
from theaios.context_router.budget import estimate_tokens
from theaios.context_router.sources import Source, register_source
from theaios.context_router.types import ContextChunk, RouteConfig, RouterConfig, SourceConfig

@register_source("faq")
class FAQSource(Source):
    FAQ = {"password": "Reset at portal.acme.com/reset", "vpn": "Download from IT portal"}

    async def fetch(self, query, config):
        chunks = []
        for term, answer in self.FAQ.items():
            if term in query.text.lower():
                chunks.append(ContextChunk(
                    content=answer, source=config.name, title=term,
                    token_count=estimate_tokens(answer),
                ))
        return chunks

config = RouterConfig(
    sources={"faq": SourceConfig(name="faq", type="faq")},
    routes=[RouteConfig(name="default", sources=["faq"])],
)
router = Router(config)
r = router.query(Query(text="How do I reset my password?"))
print(f"Chunks: {len(r.chunks)}")
for c in r.chunks:
    print(f"  [{c.title}] {c.content}")
```

---

# Part 3: Edge Cases

## 17. Empty Query Result

```bash
context-router query --config context-router.yaml --text "quantum physics" --agent external-bot
```

Expected: 0 chunks (external-bot can only see system_prompt, and "quantum physics" doesn't match any content).

---

## 18. Nonexistent Source Path

Create a config pointing to a directory that doesn't exist:

```bash
cat > bad-source.yaml << 'EOF'
version: "1.0"
sources:
  missing:
    type: directory
    path: "./nonexistent"
    patterns: ["*.md"]
routes:
  - name: default
    sources: [missing]
EOF

context-router query --config bad-source.yaml --text "anything"
```

Expected: 0 chunks, no crash. The directory source returns empty when the path doesn't exist.

---

## 19. Performance Benchmark

```python
import time
from theaios.context_router import Router, load_config, Query

config = load_config("context-router.yaml")
router = Router(config)
q = Query(text="What is the remote work policy?")

# Warm up
router.query(q)

start = time.perf_counter()
for _ in range(1000):
    router.query(q)
elapsed = time.perf_counter() - start

print(f"1,000 queries in {elapsed:.2f}s")
print(f"Average: {elapsed / 1000 * 1000:.2f}ms per query")
print(f"Throughput: {1000 / elapsed:.0f} queries/sec")
```

Expected: ~2-5ms per query for local directory sources (dominated by file I/O). Much faster with caching enabled.

---

# Summary Checklist

| # | Feature | Type | Status |
|---|---------|------|--------|
| 1 | Version/help | CLI | |
| 2 | Validate config | CLI | |
| 3 | Inspect config | CLI | |
| 4 | Query — route match | CLI | |
| 5 | Query — different route | CLI | |
| 6 | Query — default route | CLI | |
| 7 | Query — JSON output | CLI | |
| 8 | Query — permission denied | CLI | |
| 9 | Cache stats/clear | CLI | |
| 10 | Load and query | Python | |
| 11 | One-liner query | Python | |
| 12 | Iterate chunks | Python | |
| 13 | Permission filtering | Python | |
| 14 | Assemble context for LLM | Python | |
| 15 | Source registry | Python | |
| 16 | Custom source | Python | |
| 17 | Empty result | Edge | |
| 18 | Nonexistent source path | Edge | |
| 19 | Performance benchmark | Perf | |
