"""Directory context source — reads files from a local directory."""

from __future__ import annotations

import asyncio
import fnmatch
import re
from pathlib import Path

from theaios.context_router.budget import estimate_tokens
from theaios.context_router.sources import Source, register_source
from theaios.context_router.types import ContextChunk, Query, SourceConfig

_H2_SPLIT = re.compile(r"(?=^## )", re.MULTILINE)


def _matches_any(path: str, patterns: list[str]) -> bool:
    """Return True if path matches any of the glob patterns."""
    for pat in patterns:
        if fnmatch.fnmatch(path, pat):
            return True
    return False


def _split_markdown(
    content: str,
    source_name: str,
    rel_path: str,
    mtime: float,
) -> list[ContextChunk]:
    """Split markdown content by H2 headings into separate chunks."""
    sections = _H2_SPLIT.split(content)
    chunks: list[ContextChunk] = []

    for section in sections:
        section = section.strip()
        if not section:
            continue

        # Extract title from heading line
        lines = section.split("\n", 1)
        first_line = lines[0].strip()
        if first_line.startswith("## "):
            title = first_line[3:].strip()
        else:
            title = Path(rel_path).name

        chunk = ContextChunk(
            content=section,
            source=source_name,
            title=title,
            path=rel_path,
            token_count=estimate_tokens(section),
            metadata={"mtime": mtime},
        )
        chunks.append(chunk)

    return chunks


def _read_directory(config: SourceConfig) -> list[ContextChunk]:
    """Synchronous directory reading (run via asyncio.to_thread)."""
    base = Path(config.path).resolve()
    if not base.is_dir():
        return []

    chunks: list[ContextChunk] = []

    if config.recursive:
        walker = base.rglob("*")
    else:
        walker = base.glob("*")

    for file_path in walker:
        if not file_path.is_file():
            continue

        # Security: defense-in-depth check against path traversal (e.g. symlinks)
        resolved = file_path.resolve()
        if not str(resolved).startswith(str(base)):
            continue  # Skip files outside base directory

        # Get relative path for matching
        rel_path = str(file_path.relative_to(base))

        # Check include patterns
        if not _matches_any(rel_path, config.patterns):
            continue

        # Check exclude patterns
        if config.exclude_patterns and _matches_any(rel_path, config.exclude_patterns):
            continue

        # Check file size
        try:
            stat = file_path.stat()
        except OSError:
            continue

        if stat.st_size > config.max_file_size:
            continue

        mtime = stat.st_mtime

        # Read file
        try:
            content = file_path.read_text(encoding=config.encoding)
        except (OSError, UnicodeDecodeError):
            continue

        if not content.strip():
            continue

        # Markdown: split by H2 headings
        if file_path.suffix.lower() in (".md", ".markdown"):
            md_chunks = _split_markdown(content, config.name, rel_path, mtime)
            if md_chunks:
                chunks.extend(md_chunks)
            else:
                # No H2 headings — treat as single chunk
                chunk = ContextChunk(
                    content=content,
                    source=config.name,
                    title=file_path.name,
                    path=rel_path,
                    token_count=estimate_tokens(content),
                    metadata={"mtime": mtime},
                )
                chunks.append(chunk)
        else:
            # Non-markdown: one chunk per file
            chunk = ContextChunk(
                content=content,
                source=config.name,
                title=file_path.name,
                path=rel_path,
                token_count=estimate_tokens(content),
                metadata={"mtime": mtime},
            )
            chunks.append(chunk)

    return chunks


@register_source("directory")
class DirectorySource(Source):
    """Source that reads files from a local directory.

    Supports glob patterns for include/exclude, recursive traversal,
    file size limits, and automatic markdown H2 splitting.
    """

    async def fetch(self, query: Query, config: SourceConfig) -> list[ContextChunk]:
        """Read matching files from the configured directory."""
        return await asyncio.to_thread(_read_directory, config)
