"""Tests for YAML configuration loading and validation."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from theaios.context_router.config import ConfigError, load_config, validate_config
from theaios.context_router.types import RouterConfig, SourceConfig


class TestLoadConfig:
    """Tests for the load_config function."""

    def test_load_valid_yaml(self, basic_yaml: Path) -> None:
        config = load_config(str(basic_yaml))
        assert config.version == "1.0"
        assert config.metadata.name == "test-config"
        assert config.metadata.description == "A test configuration"
        assert config.metadata.author == "tester"
        assert "system_prompt" in config.sources
        assert "local_docs" in config.sources
        assert len(config.routes) == 2
        assert len(config.permissions) == 2
        assert config.budget.max_tokens == 4000
        assert config.budget.reserve_tokens == 200
        assert config.cache.enabled is False

    def test_file_not_found(self) -> None:
        with pytest.raises(FileNotFoundError, match="Config file not found"):
            load_config("/nonexistent/path/config.yaml")

    def test_invalid_yaml_not_a_mapping(self, tmp_path: Path) -> None:
        config_path = tmp_path / "bad.yaml"
        config_path.write_text("- just\n- a\n- list\n", encoding="utf-8")
        with pytest.raises(ConfigError, match="YAML mapping"):
            load_config(str(config_path))

    def test_empty_yaml(self, tmp_path: Path) -> None:
        config_path = tmp_path / "empty.yaml"
        config_path.write_text("", encoding="utf-8")
        with pytest.raises(ConfigError, match="YAML mapping"):
            load_config(str(config_path))

    def test_env_var_interpolation(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("TEST_API_KEY", "secret-key-123")
        monkeypatch.setenv("TEST_API_URL", "https://api.example.com/search")

        yaml_content = textwrap.dedent("""\
            version: "1.0"
            sources:
              api:
                type: http_api
                url: "${TEST_API_URL}"
                headers:
                  Authorization: "Bearer ${TEST_API_KEY}"
        """)
        config_path = tmp_path / "env-config.yaml"
        config_path.write_text(yaml_content, encoding="utf-8")

        config = load_config(str(config_path))
        assert config.sources["api"].url == "https://api.example.com/search"
        assert config.sources["api"].headers["Authorization"] == "Bearer secret-key-123"

    def test_env_var_missing_kept_as_is(self, tmp_path: Path) -> None:
        yaml_content = textwrap.dedent("""\
            version: "1.0"
            sources:
              api:
                type: http_api
                url: "${NONEXISTENT_VAR_12345}"
        """)
        config_path = tmp_path / "env-config.yaml"
        config_path.write_text(yaml_content, encoding="utf-8")

        config = load_config(str(config_path))
        assert config.sources["api"].url == "${NONEXISTENT_VAR_12345}"

    def test_source_parsing(self, basic_yaml: Path) -> None:
        config = load_config(str(basic_yaml))
        inline = config.sources["system_prompt"]
        assert inline.type == "inline"
        assert inline.content == "You are a helpful assistant."
        assert inline.priority == 10

        directory = config.sources["local_docs"]
        assert directory.type == "directory"
        assert "**/*.md" in directory.patterns
        assert "**/.DS_Store" in directory.exclude_patterns
        assert directory.max_file_size == 500000

    def test_route_parsing(self, basic_yaml: Path) -> None:
        config = load_config(str(basic_yaml))
        assert config.routes[0].name == "default"
        assert config.routes[0].sources == ["system_prompt", "local_docs"]
        assert config.routes[1].name == "docs-only"

    def test_permission_parsing(self, basic_yaml: Path) -> None:
        config = load_config(str(basic_yaml))
        assert config.permissions[0].agent == "*"
        assert config.permissions[0].default == "allow"
        assert config.permissions[1].agent == "restricted-bot"
        assert config.permissions[1].deny_sources == ["local_docs"]
        assert config.permissions[1].default == "deny"


class TestValidateConfig:
    """Tests for the validate_config function."""

    def test_valid_config(self, basic_config: RouterConfig) -> None:
        errors = validate_config(basic_config)
        assert errors == []

    def test_missing_source_type(self) -> None:
        config = RouterConfig(
            sources={"bad": SourceConfig(name="bad", type="")},
        )
        errors = validate_config(config)
        assert any("'type' is required" in e for e in errors)

    def test_invalid_source_type(self) -> None:
        config = RouterConfig(
            sources={"bad": SourceConfig(name="bad", type="ftp")},
        )
        errors = validate_config(config)
        assert any("invalid type 'ftp'" in e for e in errors)

    def test_inline_requires_content(self) -> None:
        config = RouterConfig(
            sources={"bad": SourceConfig(name="bad", type="inline", content="")},
        )
        errors = validate_config(config)
        assert any("inline source requires 'content'" in e for e in errors)

    def test_directory_requires_path(self) -> None:
        config = RouterConfig(
            sources={"bad": SourceConfig(name="bad", type="directory", path="")},
        )
        errors = validate_config(config)
        assert any("directory source requires 'path'" in e for e in errors)

    def test_git_repo_requires_path(self) -> None:
        config = RouterConfig(
            sources={"bad": SourceConfig(name="bad", type="git_repo", path="")},
        )
        errors = validate_config(config)
        assert any("git_repo source requires 'path'" in e for e in errors)

    def test_http_api_requires_url(self) -> None:
        config = RouterConfig(
            sources={"bad": SourceConfig(name="bad", type="http_api", url="")},
        )
        errors = validate_config(config)
        assert any("http_api source requires 'url'" in e for e in errors)

    def test_invalid_route_source_ref(self) -> None:
        from theaios.context_router.types import RouteConfig

        config = RouterConfig(
            sources={"docs": SourceConfig(name="docs", type="inline", content="hello")},
            routes=[RouteConfig(name="bad-route", sources=["nonexistent"])],
        )
        errors = validate_config(config)
        assert any("source 'nonexistent' is not defined" in e for e in errors)

    def test_duplicate_route_names(self) -> None:
        from theaios.context_router.types import RouteConfig

        config = RouterConfig(
            sources={"docs": SourceConfig(name="docs", type="inline", content="hello")},
            routes=[
                RouteConfig(name="my-route", sources=["docs"]),
                RouteConfig(name="my-route", sources=["docs"]),
            ],
        )
        errors = validate_config(config)
        assert any("duplicate route name 'my-route'" in e for e in errors)

    def test_route_missing_name(self) -> None:
        from theaios.context_router.types import RouteConfig

        config = RouterConfig(
            sources={"docs": SourceConfig(name="docs", type="inline", content="hello")},
            routes=[RouteConfig(name="", sources=["docs"])],
        )
        errors = validate_config(config)
        assert any("'name' is required" in e for e in errors)

    def test_route_missing_sources(self) -> None:
        from theaios.context_router.types import RouteConfig

        config = RouterConfig(
            sources={"docs": SourceConfig(name="docs", type="inline", content="hello")},
            routes=[RouteConfig(name="empty-route", sources=[])],
        )
        errors = validate_config(config)
        assert any("at least one source is required" in e for e in errors)

    def test_invalid_ranking(self) -> None:
        from theaios.context_router.types import BudgetConfig

        config = RouterConfig(
            budget=BudgetConfig(ranking="alphabetical"),
        )
        errors = validate_config(config)
        assert any("budget.ranking" in e and "alphabetical" in e for e in errors)

    def test_invalid_truncation(self) -> None:
        from theaios.context_router.types import BudgetConfig

        config = RouterConfig(
            budget=BudgetConfig(truncation="random"),
        )
        errors = validate_config(config)
        assert any("budget.truncation" in e and "random" in e for e in errors)

    def test_invalid_estimator(self) -> None:
        from theaios.context_router.types import BudgetConfig

        config = RouterConfig(
            budget=BudgetConfig(estimator="tiktoken"),
        )
        errors = validate_config(config)
        assert any("budget.estimator" in e and "tiktoken" in e for e in errors)

    def test_invalid_max_tokens(self) -> None:
        from theaios.context_router.types import BudgetConfig

        config = RouterConfig(
            budget=BudgetConfig(max_tokens=0),
        )
        errors = validate_config(config)
        assert any("max_tokens must be >= 1" in e for e in errors)

    def test_invalid_reserve_tokens(self) -> None:
        from theaios.context_router.types import BudgetConfig

        config = RouterConfig(
            budget=BudgetConfig(reserve_tokens=-1),
        )
        errors = validate_config(config)
        assert any("reserve_tokens must be >= 0" in e for e in errors)

    def test_invalid_cache_ttl(self) -> None:
        from theaios.context_router.types import CacheConfig

        config = RouterConfig(
            cache=CacheConfig(ttl=-1),
        )
        errors = validate_config(config)
        assert any("cache.ttl must be >= 0" in e for e in errors)

    def test_invalid_cache_max_entries(self) -> None:
        from theaios.context_router.types import CacheConfig

        config = RouterConfig(
            cache=CacheConfig(max_entries=0),
        )
        errors = validate_config(config)
        assert any("cache.max_entries must be >= 1" in e for e in errors)

    def test_invalid_default_permission(self) -> None:
        from theaios.context_router.types import PermissionConfig

        config = RouterConfig(
            permissions=[PermissionConfig(default="maybe")],
        )
        errors = validate_config(config)
        assert any("invalid default 'maybe'" in e for e in errors)

    def test_unsupported_version(self) -> None:
        config = RouterConfig(version="2.0")
        errors = validate_config(config)
        assert any("Unsupported config version" in e for e in errors)
