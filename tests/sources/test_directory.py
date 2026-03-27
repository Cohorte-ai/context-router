"""Tests for the directory context source."""

from __future__ import annotations

from pathlib import Path

import pytest

from theaios.context_router.sources import get_source
from theaios.context_router.types import Query, SourceConfig


class TestDirectorySource:
    """Tests for DirectorySource.fetch()."""

    @pytest.fixture()
    def source(self):
        return get_source("directory")

    @pytest.fixture()
    def query(self):
        return Query(text="test query")

    @pytest.mark.asyncio
    async def test_reads_md_and_txt_files(self, source, query, sample_data_dir: Path) -> None:
        config = SourceConfig(
            name="docs",
            type="directory",
            path=str(sample_data_dir),
            patterns=["*", "**/*"],
        )
        chunks = await source.fetch(query, config)

        # Should find notes.txt, policy.md (split into sections), faq.txt,
        # archive/old_notes.txt, .DS_Store
        source_names = {c.source for c in chunks}
        assert all(s == "docs" for s in source_names)
        assert len(chunks) >= 4  # at least the 4 real files (md may split into sections)

    @pytest.mark.asyncio
    async def test_respects_glob_patterns(self, source, query, sample_data_dir: Path) -> None:
        config = SourceConfig(
            name="docs",
            type="directory",
            path=str(sample_data_dir),
            patterns=["*.md", "**/*.md"],
        )
        chunks = await source.fetch(query, config)

        # Only .md files should be included
        paths = {c.path for c in chunks}
        assert all(p.endswith(".md") or p == "" for p in paths)
        assert len(chunks) >= 1

    @pytest.mark.asyncio
    async def test_respects_exclude_patterns(self, source, query, sample_data_dir: Path) -> None:
        config = SourceConfig(
            name="docs",
            type="directory",
            path=str(sample_data_dir),
            patterns=["*", "**/*"],
            exclude_patterns=["archive/*", ".DS_Store"],
        )
        chunks = await source.fetch(query, config)

        paths = {c.path for c in chunks}
        assert not any("archive" in p for p in paths)
        assert ".DS_Store" not in paths

    @pytest.mark.asyncio
    async def test_splits_markdown_by_h2(self, source, query, sample_data_dir: Path) -> None:
        config = SourceConfig(
            name="docs",
            type="directory",
            path=str(sample_data_dir),
            patterns=["policy.md"],
        )
        chunks = await source.fetch(query, config)

        # policy.md has two H2 sections: "Remote Work" and "Travel"
        titles = [c.title for c in chunks]
        assert "Remote Work" in titles
        assert "Travel" in titles

    @pytest.mark.asyncio
    async def test_respects_max_file_size(self, source, query, tmp_path: Path) -> None:
        data_dir = tmp_path / "size_test"
        data_dir.mkdir()

        # Create a small file (under limit)
        (data_dir / "small.txt").write_text("Small file content.", encoding="utf-8")

        # Create a large file (over limit)
        (data_dir / "large.txt").write_text("x" * 500, encoding="utf-8")

        config = SourceConfig(
            name="docs",
            type="directory",
            path=str(data_dir),
            patterns=["*", "**/*"],
            max_file_size=100,  # 100 bytes limit
        )
        chunks = await source.fetch(query, config)

        paths = [c.path for c in chunks]
        assert "small.txt" in paths
        assert "large.txt" not in paths

    @pytest.mark.asyncio
    async def test_sets_path_title_mtime(self, source, query, sample_data_dir: Path) -> None:
        config = SourceConfig(
            name="docs",
            type="directory",
            path=str(sample_data_dir),
            patterns=["notes.txt"],
        )
        chunks = await source.fetch(query, config)

        assert len(chunks) == 1
        chunk = chunks[0]
        assert chunk.path == "notes.txt"
        assert chunk.title == "notes.txt"
        assert "mtime" in chunk.metadata
        assert isinstance(chunk.metadata["mtime"], float)

    @pytest.mark.asyncio
    async def test_nonexistent_directory_returns_empty(self, source, query) -> None:
        config = SourceConfig(
            name="docs",
            type="directory",
            path="/nonexistent/path/to/dir",
            patterns=["**/*"],
        )
        chunks = await source.fetch(query, config)
        assert chunks == []

    @pytest.mark.asyncio
    async def test_empty_directory_returns_empty(self, source, query, tmp_path: Path) -> None:
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()

        config = SourceConfig(
            name="docs",
            type="directory",
            path=str(empty_dir),
            patterns=["**/*"],
        )
        chunks = await source.fetch(query, config)
        assert chunks == []

    @pytest.mark.asyncio
    async def test_non_recursive(self, source, query, sample_data_dir: Path) -> None:
        config = SourceConfig(
            name="docs",
            type="directory",
            path=str(sample_data_dir),
            patterns=["*"],
            recursive=False,
        )
        chunks = await source.fetch(query, config)

        # Should not include files in archive/ subdirectory
        paths = [c.path for c in chunks]
        assert not any("archive" in p for p in paths)

    @pytest.mark.asyncio
    async def test_markdown_without_h2_returns_single_chunk(
        self, source, query, tmp_path: Path
    ) -> None:
        data_dir = tmp_path / "no_h2"
        data_dir.mkdir()
        (data_dir / "simple.md").write_text(
            "# Title\n\nJust a simple document without H2 headings.\n",
            encoding="utf-8",
        )

        config = SourceConfig(
            name="docs",
            type="directory",
            path=str(data_dir),
            patterns=["*.md", "**/*.md"],
        )
        chunks = await source.fetch(query, config)
        assert len(chunks) == 1
        assert chunks[0].title == "simple.md"
