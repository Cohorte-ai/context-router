"""Tests for the source registry."""

from __future__ import annotations

import pytest

from theaios.context_router.sources import Source, get_source, list_sources


class TestSourceRegistry:
    """Tests for built-in source registration and lookup."""

    def test_built_in_sources_registered(self) -> None:
        available = list_sources()
        assert "directory" in available
        assert "git_repo" in available
        assert "http_api" in available
        assert "inline" in available

    def test_built_in_count(self) -> None:
        assert len(list_sources()) == 4

    def test_get_source_returns_instance(self) -> None:
        source = get_source("inline")
        assert isinstance(source, Source)

    def test_get_source_directory(self) -> None:
        source = get_source("directory")
        assert isinstance(source, Source)

    def test_get_source_http_api(self) -> None:
        source = get_source("http_api")
        assert isinstance(source, Source)

    def test_get_source_git_repo(self) -> None:
        source = get_source("git_repo")
        assert isinstance(source, Source)

    def test_unknown_source_raises_key_error(self) -> None:
        with pytest.raises(KeyError, match="Unknown source type 'ftp'"):
            get_source("ftp")

    def test_unknown_source_shows_available(self) -> None:
        with pytest.raises(KeyError, match="Available:"):
            get_source("nonexistent")

    def test_list_sources_is_sorted(self) -> None:
        sources = list_sources()
        assert sources == sorted(sources)
