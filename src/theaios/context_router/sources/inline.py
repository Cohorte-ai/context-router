"""Inline context source — returns static content from config."""

from __future__ import annotations

from theaios.context_router.budget import estimate_tokens
from theaios.context_router.sources import Source, register_source
from theaios.context_router.types import ContextChunk, Query, SourceConfig


@register_source("inline")
class InlineSource(Source):
    """Source that returns content directly from the SourceConfig.content field.

    Useful for embedding static context (system prompts, instructions,
    boilerplate) directly in the router configuration.
    """

    async def fetch(self, query: Query, config: SourceConfig) -> list[ContextChunk]:
        """Return a single chunk containing the inline content."""
        if not config.content:
            return []

        chunk = ContextChunk(
            content=config.content,
            source=config.name,
            title=config.name,
            token_count=estimate_tokens(config.content),
        )
        return [chunk]
