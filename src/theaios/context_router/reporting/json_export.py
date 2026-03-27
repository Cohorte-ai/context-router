"""JSON export for context routing results."""

from __future__ import annotations

import json
from pathlib import Path

from theaios.context_router.types import ContextResponse


def export_response_json(
    response: ContextResponse,
    output_path: str | None = None,
) -> str:
    """Export a context response as JSON.

    Parameters
    ----------
    response : ContextResponse
        The context response to export.
    output_path : str | None
        If provided, write the JSON to this file path.
        If None, return the JSON string only.

    Returns
    -------
    str
        The JSON-encoded response.
    """
    data: dict[str, object] = {
        "total_tokens": response.total_tokens,
        "was_truncated": response.was_truncated,
        "matched_routes": response.matched_routes,
        "denied_sources": response.denied_sources,
        "evaluation_time_ms": round(response.evaluation_time_ms, 3),
        "chunks": [
            {
                "content": chunk.content,
                "source": chunk.source,
                "title": chunk.title,
                "path": chunk.path,
                "relevance_score": round(chunk.relevance_score, 4),
                "token_count": chunk.token_count,
                "metadata": chunk.metadata,
            }
            for chunk in response.chunks
        ],
    }

    json_str = json.dumps(data, indent=2, default=str)

    if output_path is not None:
        Path(output_path).write_text(json_str, encoding="utf-8")

    return json_str
