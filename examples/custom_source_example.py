"""Custom source example — extend the router with your own data backend."""

from __future__ import annotations

from theaios.context_router import Query, Router
from theaios.context_router.budget import estimate_tokens
from theaios.context_router.sources import Source, register_source
from theaios.context_router.types import (
    ContextChunk,
    RouteConfig,
    RouterConfig,
    SourceConfig,
)


# 1. Define your custom source
@register_source("dictionary")
class DictionarySource(Source):
    """A source that looks up terms in an in-memory dictionary.

    In production, this could query a database, search engine, or API.
    """

    KNOWLEDGE = {
        "okr": "OKR (Objectives and Key Results) is a goal-setting framework used to define "
        "measurable goals and track outcomes. Each OKR has one Objective (qualitative) "
        "and 2-5 Key Results (quantitative).",
        "sprint": "A sprint is a fixed time period (usually 2 weeks) during which a team "
        "completes a set of planned work items. Sprints are a core practice in Scrum.",
        "standup": "A daily standup is a short (15 min) meeting where team members share "
        "what they did yesterday, what they'll do today, and any blockers.",
        "retrospective": "A retrospective is a meeting held at the end of each sprint to "
        "reflect on what went well, what didn't, and what to improve.",
    }

    async def fetch(self, query: Query, config: SourceConfig) -> list[ContextChunk]:
        chunks = []
        query_lower = query.text.lower()
        for term, definition in self.KNOWLEDGE.items():
            if term in query_lower:
                chunks.append(
                    ContextChunk(
                        content=definition,
                        source=config.name,
                        title=term.upper(),
                        token_count=estimate_tokens(definition),
                    )
                )
        return chunks


# 2. Use it in a config (programmatic)
config = RouterConfig(
    sources={
        "glossary": SourceConfig(name="glossary", type="dictionary"),
    },
    routes=[RouteConfig(name="default", sources=["glossary"])],
)

router = Router(config)

# 3. Query
for question in [
    "What is an OKR?",
    "How does a sprint retrospective work?",
    "What is the weather today?",
]:
    response = router.query(Query(text=question))
    if response.chunks:
        print(f"Q: {question}")
        for chunk in response.chunks:
            print(f"  [{chunk.title}] {chunk.content[:100]}...")
    else:
        print(f"Q: {question}")
        print(f"  No context found")
    print()
