"""Regression tests for the 0.2.4 pre-release usability test: config mistakes that used to load
silently and change which context an agent gets."""

from __future__ import annotations

from pathlib import Path

import pytest

from theaios.context_router.config import ConfigError, load_config
from theaios.context_router.engine import Router
from theaios.context_router.types import RouteConfig, RouterConfig, SourceConfig

BASE = """
version: "1.0"
sources:
  docs:
    type: inline
    content: "Handbook"
"""
ROUTE = """
routes:
  - name: r
    when: 'agent == "a"'
    sources: [docs]
"""


def _errors(tmp_path: Path, body: str) -> str:
    path = tmp_path / "context-router.yaml"
    path.write_text(BASE + body)
    with pytest.raises(ConfigError) as exc:
        load_config(str(path))
    return "\n".join(exc.value.errors)


def test_routes_as_mapping_is_rejected(tmp_path: Path) -> None:
    body = "routes:\n  r: {when: 'agent == \"a\"', sources: [docs]}\n"
    assert "'routes' must be a list" in _errors(tmp_path, body)


def test_unknown_route_key_is_rejected(tmp_path: Path) -> None:
    errors = _errors(tmp_path, ROUTE + "    enabeld: false\n")
    assert "routes[0] (r): unknown key 'enabeld' (did you mean 'enabled'?)" in errors


def test_quoted_enabled_is_rejected(tmp_path: Path) -> None:
    assert "'enabled' must be true or false" in _errors(tmp_path, ROUTE + '    enabled: "false"\n')


def test_non_string_when_is_rejected(tmp_path: Path) -> None:
    body = ROUTE.replace("when: 'agent == \"a\"'", "when: 42")
    assert "'when' must be a string" in _errors(tmp_path, body)


def test_not_a_config_file_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "mkdocs.yml"
    path.write_text("site_name: Docs\n")
    with pytest.raises(ConfigError, match="unknown key 'site_name'"):
        load_config(str(path))


def test_yaml_syntax_error_and_directory_are_config_errors(tmp_path: Path) -> None:
    path = tmp_path / "bad.yaml"
    path.write_text("routes: [\n")
    with pytest.raises(ConfigError, match="YAML syntax error"):
        load_config(str(path))
    with pytest.raises(ConfigError, match="is not a file"):
        load_config(str(tmp_path))


def test_router_built_in_code_is_validated() -> None:
    config = RouterConfig(
        sources={"docs": SourceConfig(name="docs", type="inline", content="x")},
        routes=[RouteConfig(name="r", when="agent == 'a'", sources=["missing"])],
    )
    with pytest.raises(ConfigError, match="source 'missing' is not defined"):
        Router(config)
