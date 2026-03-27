"""Git repository context source — reads files from a git ref."""

from __future__ import annotations

import asyncio
import fnmatch
import re
import subprocess

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


def _split_markdown_git(
    content: str,
    source_name: str,
    file_path: str,
) -> list[ContextChunk]:
    """Split markdown content by H2 headings into separate chunks."""
    sections = _H2_SPLIT.split(content)
    chunks: list[ContextChunk] = []

    for section in sections:
        section = section.strip()
        if not section:
            continue

        lines = section.split("\n", 1)
        first_line = lines[0].strip()
        if first_line.startswith("## "):
            title = first_line[3:].strip()
        else:
            # Use filename as title
            title = file_path.rsplit("/", 1)[-1] if "/" in file_path else file_path

        chunk = ContextChunk(
            content=section,
            source=source_name,
            title=title,
            path=file_path,
            token_count=estimate_tokens(section),
            metadata={"ref": "HEAD"},
        )
        chunks.append(chunk)

    return chunks


def _read_git_repo(config: SourceConfig) -> list[ContextChunk]:
    """Synchronous git repository reading (run via asyncio.to_thread)."""
    repo_path = config.path
    ref = config.ref

    # List files in the git tree
    try:
        result = subprocess.run(
            ["git", "ls-tree", "-r", "--name-only", ref],
            cwd=repo_path,
            capture_output=True,
            text=True,
            check=True,
            timeout=30,
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
        return []

    file_paths = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    chunks: list[ContextChunk] = []

    for file_path in file_paths:
        # Check include patterns
        if not _matches_any(file_path, config.patterns):
            continue

        # Check exclude patterns
        if config.exclude_patterns and _matches_any(file_path, config.exclude_patterns):
            continue

        # Read file content from git
        try:
            cat_result = subprocess.run(
                ["git", "show", f"{ref}:{file_path}"],
                cwd=repo_path,
                capture_output=True,
                text=True,
                check=True,
                timeout=10,
            )
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            continue

        content = cat_result.stdout
        if not content.strip():
            continue

        # Check content size (approximate — git show returns text)
        if len(content.encode("utf-8", errors="replace")) > config.max_file_size:
            continue

        # Markdown: split by H2 headings
        is_markdown = file_path.lower().endswith((".md", ".markdown"))
        if is_markdown:
            md_chunks = _split_markdown_git(content, config.name, file_path)
            if md_chunks:
                # Update ref in metadata
                for c in md_chunks:
                    c.metadata["ref"] = ref
                chunks.extend(md_chunks)
            else:
                title = file_path.rsplit("/", 1)[-1] if "/" in file_path else file_path
                chunk = ContextChunk(
                    content=content,
                    source=config.name,
                    title=title,
                    path=file_path,
                    token_count=estimate_tokens(content),
                    metadata={"ref": ref},
                )
                chunks.append(chunk)
        else:
            title = file_path.rsplit("/", 1)[-1] if "/" in file_path else file_path
            chunk = ContextChunk(
                content=content,
                source=config.name,
                title=title,
                path=file_path,
                token_count=estimate_tokens(content),
                metadata={"ref": ref},
            )
            chunks.append(chunk)

    return chunks


@register_source("git_repo")
class GitRepoSource(Source):
    """Source that reads files from a git repository at a specific ref.

    Uses ``git ls-tree`` to enumerate files and ``git show`` to read content.
    Supports glob pattern matching and markdown H2 splitting.
    """

    async def fetch(self, query: Query, config: SourceConfig) -> list[ContextChunk]:
        """Read matching files from the configured git repository."""
        return await asyncio.to_thread(_read_git_repo, config)
