"""Tests for the inline context source."""

from __future__ import annotations

import pytest

from theaios.context_router.sources import get_source
from theaios.context_router.types import Query, SourceConfig


class TestInlineSource:
    """Tests for InlineSource.fetch()."""

    @pytest.fixture()
    def source(self):
        return get_source("inline")

    @pytest.fixture()
    def query(self):
        return Query(text="test query")

    @pytest.mark.asyncio
    async def test_returns_content_as_single_chunk(self, source, query) -> None:
        config = SourceConfig(
            name="system-prompt",
            type="inline",
            content="You are a helpful assistant. Be concise and accurate.",
        )
        chunks = await source.fetch(query, config)

        assert len(chunks) == 1
        assert chunks[0].content == "You are a helpful assistant. Be concise and accurate."
        assert chunks[0].source == "system-prompt"
        assert chunks[0].title == "system-prompt"

    @pytest.mark.asyncio
    async def test_empty_content_returns_empty_list(self, source, query) -> None:
        config = SourceConfig(name="empty", type="inline", content="")
        chunks = await source.fetch(query, config)
        assert chunks == []

    @pytest.mark.asyncio
    async def test_token_count_is_set(self, source, query) -> None:
        config = SourceConfig(
            name="prompt",
            type="inline",
            content="Hello world",
        )
        chunks = await source.fetch(query, config)
        assert len(chunks) == 1
        assert chunks[0].token_count > 0

    @pytest.mark.asyncio
    async def test_multiline_content(self, source, query) -> None:
        content = "Line one.\nLine two.\nLine three."
        config = SourceConfig(name="multi", type="inline", content=content)
        chunks = await source.fetch(query, config)
        assert len(chunks) == 1
        assert "Line one." in chunks[0].content
        assert "Line three." in chunks[0].content
