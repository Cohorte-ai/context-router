"""Tests for the HTTP API context source."""

from __future__ import annotations

import json

import httpx
import pytest
import respx

from theaios.context_router.sources import get_source
from theaios.context_router.types import Query, SourceConfig


class TestHttpApiSource:
    """Tests for HttpApiSource.fetch()."""

    @pytest.fixture()
    def source(self):
        return get_source("http_api")

    @pytest.fixture()
    def query(self):
        return Query(text="remote work policy")

    @pytest.mark.asyncio
    @respx.mock
    async def test_get_request_with_json_response(self, source, query) -> None:
        respx.get("https://api.example.com/search?q=remote+work+policy").mock(
            return_value=httpx.Response(
                200,
                json={
                    "results": [
                        {"text": "Remote work is allowed.", "title": "Policy"},
                        {"text": "VPN required for access.", "title": "Security"},
                    ]
                },
            )
        )

        config = SourceConfig(
            name="api",
            type="http_api",
            url="https://api.example.com/search?q=remote+work+policy",
            method="GET",
            response_path="results",
            result_text_field="text",
            result_title_field="title",
        )
        chunks = await source.fetch(query, config)

        assert len(chunks) == 2
        assert chunks[0].content == "Remote work is allowed."
        assert chunks[0].title == "Policy"
        assert chunks[1].content == "VPN required for access."
        assert chunks[1].title == "Security"
        assert chunks[0].source == "api"

    @pytest.mark.asyncio
    @respx.mock
    async def test_post_with_body_template_and_query_substitution(self, source, query) -> None:
        respx.post("https://api.example.com/search").mock(
            return_value=httpx.Response(
                200,
                json={"data": [{"text": "Found relevant document.", "title": "Result 1"}]},
            )
        )

        config = SourceConfig(
            name="api",
            type="http_api",
            url="https://api.example.com/search",
            method="POST",
            body_template='{"query": "{{query}}", "limit": 5}',
            response_path="data",
            result_text_field="text",
            result_title_field="title",
        )
        chunks = await source.fetch(query, config)

        assert len(chunks) == 1
        assert chunks[0].content == "Found relevant document."

        # Verify the request was made with the substituted body
        request = respx.calls[0].request
        body = json.loads(request.content)
        assert body["query"] == "remote work policy"
        assert body["limit"] == 5

    @pytest.mark.asyncio
    @respx.mock
    async def test_response_path_navigation(self, source, query) -> None:
        respx.get("https://api.example.com/deep").mock(
            return_value=httpx.Response(
                200,
                json={"response": {"hits": {"items": [{"text": "Deep result", "title": "Deep"}]}}},
            )
        )

        config = SourceConfig(
            name="api",
            type="http_api",
            url="https://api.example.com/deep",
            response_path="response.hits.items",
            result_text_field="text",
            result_title_field="title",
        )
        chunks = await source.fetch(query, config)

        assert len(chunks) == 1
        assert chunks[0].content == "Deep result"
        assert chunks[0].title == "Deep"

    @pytest.mark.asyncio
    @respx.mock
    async def test_result_text_field_extraction(self, source, query) -> None:
        respx.get("https://api.example.com/custom").mock(
            return_value=httpx.Response(
                200,
                json={"results": [{"body": "Custom field content.", "name": "Custom Title"}]},
            )
        )

        config = SourceConfig(
            name="api",
            type="http_api",
            url="https://api.example.com/custom",
            response_path="results",
            result_text_field="body",
            result_title_field="name",
        )
        chunks = await source.fetch(query, config)

        assert len(chunks) == 1
        assert chunks[0].content == "Custom field content."
        assert chunks[0].title == "Custom Title"

    @pytest.mark.asyncio
    @respx.mock
    async def test_timeout_handling(self, source, query) -> None:
        respx.get("https://api.example.com/slow").mock(
            side_effect=httpx.ReadTimeout("Connection timed out")
        )

        config = SourceConfig(
            name="api",
            type="http_api",
            url="https://api.example.com/slow",
        )
        chunks = await source.fetch(query, config)
        assert chunks == []

    @pytest.mark.asyncio
    @respx.mock
    async def test_error_response_non_fatal(self, source, query) -> None:
        respx.get("https://api.example.com/error").mock(
            return_value=httpx.Response(500, text="Internal Server Error")
        )

        config = SourceConfig(
            name="api",
            type="http_api",
            url="https://api.example.com/error",
        )
        chunks = await source.fetch(query, config)
        assert chunks == []

    @pytest.mark.asyncio
    @respx.mock
    async def test_404_response(self, source, query) -> None:
        respx.get("https://api.example.com/notfound").mock(
            return_value=httpx.Response(404, text="Not Found")
        )

        config = SourceConfig(
            name="api",
            type="http_api",
            url="https://api.example.com/notfound",
        )
        chunks = await source.fetch(query, config)
        assert chunks == []

    @pytest.mark.asyncio
    @respx.mock
    async def test_empty_url_returns_empty(self, source, query) -> None:
        config = SourceConfig(name="api", type="http_api", url="")
        chunks = await source.fetch(query, config)
        assert chunks == []

    @pytest.mark.asyncio
    @respx.mock
    async def test_non_json_response_returned_as_chunk(self, source, query) -> None:
        respx.get("https://api.example.com/text").mock(
            return_value=httpx.Response(
                200,
                text="This is plain text content.",
                headers={"Content-Type": "text/plain"},
            )
        )

        config = SourceConfig(
            name="api",
            type="http_api",
            url="https://api.example.com/text",
        )
        chunks = await source.fetch(query, config)
        assert len(chunks) == 1
        assert chunks[0].content == "This is plain text content."

    @pytest.mark.asyncio
    @respx.mock
    async def test_token_count_is_set(self, source, query) -> None:
        respx.get("https://api.example.com/data").mock(
            return_value=httpx.Response(
                200,
                json={"results": [{"text": "Some content", "title": "Doc"}]},
            )
        )

        config = SourceConfig(
            name="api",
            type="http_api",
            url="https://api.example.com/data",
            response_path="results",
        )
        chunks = await source.fetch(query, config)
        assert len(chunks) == 1
        assert chunks[0].token_count > 0

    @pytest.mark.asyncio
    @respx.mock
    async def test_url_query_substitution(self, source, query) -> None:
        respx.get("https://api.example.com/search?q=remote%20work%20policy").mock(
            return_value=httpx.Response(200, json={"results": []})
        )

        config = SourceConfig(
            name="api",
            type="http_api",
            url="https://api.example.com/search?q={{query}}",
            response_path="results",
        )
        chunks = await source.fetch(query, config)
        assert chunks == []

    @pytest.mark.asyncio
    @respx.mock
    async def test_custom_headers(self, source, query) -> None:
        respx.get("https://api.example.com/auth").mock(
            return_value=httpx.Response(200, json={"results": []})
        )

        config = SourceConfig(
            name="api",
            type="http_api",
            url="https://api.example.com/auth",
            headers={"Authorization": "Bearer test-token", "X-Custom": "value"},
            response_path="results",
        )
        await source.fetch(query, config)

        request = respx.calls[0].request
        assert request.headers["Authorization"] == "Bearer test-token"
        assert request.headers["X-Custom"] == "value"
