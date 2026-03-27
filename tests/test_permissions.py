"""Tests for permission resolution and filtering."""

from __future__ import annotations


from theaios.context_router.permissions import (
    ResolvedPermission,
    filter_by_path,
    filter_by_source,
    resolve_permission,
)
from theaios.context_router.types import ContextChunk, PermissionConfig, SourceConfig


class TestResolvePermission:
    """Tests for resolve_permission()."""

    def test_listed_agent_exact_match(self) -> None:
        permissions = [
            PermissionConfig(
                agent="hr-bot",
                allow_sources=["policies"],
                deny_sources=["secrets"],
                deny_paths=["**/internal/*"],
                default="deny",
            ),
        ]
        result = resolve_permission("hr-bot", permissions)

        assert result.agent == "hr-bot"
        assert "policies" in result.allowed_sources
        assert "secrets" in result.denied_sources
        assert "**/internal/*" in result.deny_paths
        assert result.default == "deny"

    def test_wildcard_match(self) -> None:
        permissions = [
            PermissionConfig(
                agent="*",
                allow_sources=["docs"],
                default="allow",
            ),
        ]
        result = resolve_permission("any-agent", permissions)
        assert "docs" in result.allowed_sources
        assert result.default == "allow"

    def test_unlisted_agent_default_deny(self) -> None:
        permissions = [
            PermissionConfig(
                agent="specific-bot",
                allow_sources=["docs"],
                default="deny",
            ),
        ]
        # Query with a different agent that has no matching rule
        result = resolve_permission("other-bot", permissions)
        # No rules matched, so default is "allow" (the fallback)
        assert result.default == "allow"

    def test_unlisted_agent_default_allow(self) -> None:
        permissions = [
            PermissionConfig(
                agent="admin-bot",
                allow_sources=["everything"],
                default="allow",
            ),
        ]
        result = resolve_permission("random-agent", permissions)
        assert result.default == "allow"

    def test_multiple_rules_merged(self) -> None:
        permissions = [
            PermissionConfig(
                agent="*",
                allow_sources=["docs"],
                default="allow",
            ),
            PermissionConfig(
                agent="hr-bot",
                allow_sources=["policies"],
                deny_sources=["secrets"],
                deny_paths=["**/confidential/*"],
                default="deny",
            ),
        ]
        result = resolve_permission("hr-bot", permissions)

        # Both rules matched (wildcard + exact), merged
        assert "docs" in result.allowed_sources
        assert "policies" in result.allowed_sources
        assert "secrets" in result.denied_sources
        assert "**/confidential/*" in result.deny_paths
        # Most restrictive default wins
        assert result.default == "deny"

    def test_no_permissions_defaults_to_allow(self) -> None:
        result = resolve_permission("any-agent", [])
        assert result.default == "allow"
        assert result.allowed_sources == set()
        assert result.denied_sources == set()


class TestFilterBySource:
    """Tests for filter_by_source()."""

    def test_allow_by_default(self) -> None:
        sources = {
            "docs": SourceConfig(name="docs", type="directory", path="/data"),
            "api": SourceConfig(name="api", type="http_api", url="http://example.com"),
        }
        permission = ResolvedPermission(agent="test", default="allow")

        allowed, denied = filter_by_source(sources, permission)
        assert set(allowed) == {"docs", "api"}
        assert denied == []

    def test_deny_by_default(self) -> None:
        sources = {
            "docs": SourceConfig(name="docs", type="directory", path="/data"),
            "api": SourceConfig(name="api", type="http_api", url="http://example.com"),
        }
        permission = ResolvedPermission(agent="test", default="deny")

        allowed, denied = filter_by_source(sources, permission)
        assert allowed == []
        assert set(denied) == {"docs", "api"}

    def test_explicit_allow_overrides_deny_default(self) -> None:
        sources = {
            "docs": SourceConfig(name="docs", type="directory", path="/data"),
            "secrets": SourceConfig(name="secrets", type="directory", path="/secrets"),
        }
        permission = ResolvedPermission(
            agent="test",
            allowed_sources={"docs"},
            default="deny",
        )

        allowed, denied = filter_by_source(sources, permission)
        assert allowed == ["docs"]
        assert denied == ["secrets"]

    def test_explicit_deny_overrides_allow_default(self) -> None:
        sources = {
            "docs": SourceConfig(name="docs", type="directory", path="/data"),
            "secrets": SourceConfig(name="secrets", type="directory", path="/secrets"),
        }
        permission = ResolvedPermission(
            agent="test",
            denied_sources={"secrets"},
            default="allow",
        )

        allowed, denied = filter_by_source(sources, permission)
        assert allowed == ["docs"]
        assert denied == ["secrets"]

    def test_deny_takes_precedence_over_allow(self) -> None:
        sources = {
            "docs": SourceConfig(name="docs", type="directory", path="/data"),
        }
        permission = ResolvedPermission(
            agent="test",
            allowed_sources={"docs"},
            denied_sources={"docs"},
            default="allow",
        )

        allowed, denied = filter_by_source(sources, permission)
        assert allowed == []
        assert denied == ["docs"]


class TestFilterByPath:
    """Tests for filter_by_path()."""

    def test_no_deny_paths_passes_all(self) -> None:
        chunks = [
            ContextChunk(content="a", source="s", path="docs/readme.md"),
            ContextChunk(content="b", source="s", path="internal/secret.md"),
        ]
        result = filter_by_path(chunks, [])
        assert len(result) == 2

    def test_glob_matching_denies_paths(self) -> None:
        chunks = [
            ContextChunk(content="public", source="s", path="docs/readme.md"),
            ContextChunk(content="secret", source="s", path="internal/secret.md"),
            ContextChunk(content="config", source="s", path="internal/config.yaml"),
        ]
        result = filter_by_path(chunks, ["internal/*"])

        assert len(result) == 1
        assert result[0].path == "docs/readme.md"

    def test_multiple_deny_patterns(self) -> None:
        chunks = [
            ContextChunk(content="a", source="s", path="docs/readme.md"),
            ContextChunk(content="b", source="s", path="secret/keys.txt"),
            ContextChunk(content="c", source="s", path="archive/old.txt"),
        ]
        result = filter_by_path(chunks, ["secret/*", "archive/*"])
        assert len(result) == 1
        assert result[0].path == "docs/readme.md"

    def test_chunks_without_path_pass_through(self) -> None:
        chunks = [
            ContextChunk(content="inline", source="s", path=""),
            ContextChunk(content="file", source="s", path="docs/readme.md"),
        ]
        result = filter_by_path(chunks, ["docs/*"])

        assert len(result) == 1
        assert result[0].content == "inline"

    def test_wildcard_deny_path(self) -> None:
        chunks = [
            ContextChunk(content="a", source="s", path="anything.txt"),
        ]
        result = filter_by_path(chunks, ["*"])
        assert result == []
