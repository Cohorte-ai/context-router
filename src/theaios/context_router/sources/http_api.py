"""HTTP API context source — queries a REST endpoint."""

from __future__ import annotations

import ipaddress
from urllib.parse import urlparse

import httpx

from theaios.context_router.budget import estimate_tokens
from theaios.context_router.sources import Source, register_source
from theaios.context_router.types import ContextChunk, Query, SourceConfig


def _validate_url(url: str) -> None:
    """Validate a URL to prevent SSRF attacks.

    Rejects non-HTTP(S) schemes and private/internal IP addresses.
    """
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"Only http/https URLs allowed, got: {parsed.scheme}")
    hostname = parsed.hostname or ""
    try:
        ip = ipaddress.ip_address(hostname)
        if ip.is_private or ip.is_loopback or ip.is_link_local:
            raise ValueError(f"Private/internal IP addresses not allowed: {hostname}")
    except ValueError as exc:
        # Re-raise our own ValueError (SSRF block), but ignore parse errors
        # (hostname is not an IP literal, which is fine)
        if "not allowed" in str(exc):
            raise


def _navigate_path(data: object, path: str) -> object:
    """Navigate a dot-notation path through a nested dict/list structure.

    Examples::

        _navigate_path({"results": [{"text": "hello"}]}, "results") -> [{"text": "hello"}]
        _navigate_path({"a": {"b": [1, 2]}}, "a.b") -> [1, 2]
    """
    if not path:
        return data

    current: object = data
    for part in path.split("."):
        if isinstance(current, dict):
            current = current.get(part)
        elif isinstance(current, list) and part.isdigit():
            idx = int(part)
            if 0 <= idx < len(current):
                current = current[idx]
            else:
                return None
        else:
            return None
    return current


@register_source("http_api")
class HttpApiSource(Source):
    """Source that queries a REST API endpoint.

    Supports GET and POST methods, template substitution for query text,
    JSON response parsing with dot-notation path navigation, and
    configurable text/title field extraction.
    """

    async def fetch(self, query: Query, config: SourceConfig) -> list[ContextChunk]:
        """Query the configured HTTP endpoint and parse the response."""
        if not config.url:
            return []

        # Build request
        url = config.url.replace("{{query}}", query.text)

        # Security: validate URL to prevent SSRF
        _validate_url(url)
        headers = dict(config.headers)

        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                if config.method.upper() == "POST":
                    body = config.body_template.replace("{{query}}", query.text)
                    if "Content-Type" not in headers:
                        headers["Content-Type"] = "application/json"
                    response = await client.post(url, content=body, headers=headers)
                else:
                    response = await client.get(url, headers=headers)

                response.raise_for_status()
            except (httpx.HTTPError, httpx.InvalidURL):
                return []

        # Parse JSON response
        try:
            data = response.json()
        except (ValueError, TypeError):
            # Non-JSON response — return as single chunk
            text = response.text
            if not text.strip():
                return []
            chunk = ContextChunk(
                content=text,
                source=config.name,
                title=config.name,
                token_count=estimate_tokens(text),
            )
            return [chunk]

        # Navigate to the results using response_path
        results = _navigate_path(data, config.response_path)

        # Normalize to list
        if isinstance(results, dict):
            results = [results]
        elif not isinstance(results, list):
            # Scalar or None — wrap in a dict for uniform handling
            if results is not None:
                text = str(results)
                chunk = ContextChunk(
                    content=text,
                    source=config.name,
                    title=config.name,
                    token_count=estimate_tokens(text),
                )
                return [chunk]
            return []

        # Extract chunks from result items
        chunks: list[ContextChunk] = []
        for item in results:
            if isinstance(item, dict):
                text_val = item.get(config.result_text_field)
                title_val = item.get(config.result_title_field)
                text = str(text_val) if text_val is not None else ""
                title = str(title_val) if title_val is not None else ""
            elif isinstance(item, str):
                text = item
                title = ""
            else:
                text = str(item) if item is not None else ""
                title = ""

            if not text.strip():
                continue

            chunk = ContextChunk(
                content=text,
                source=config.name,
                title=title,
                token_count=estimate_tokens(text),
                metadata={"url": config.url},
            )
            chunks.append(chunk)

        return chunks
