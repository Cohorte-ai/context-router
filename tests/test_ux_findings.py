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


# --- Re-verification findings ------------------------------------------------------------


def test_custom_source_type_registered_in_code_is_accepted() -> None:
    from theaios.context_router.sources import Source, register_source
    from theaios.context_router.types import ContextChunk, Query

    @register_source("ux_test_dictionary")
    class _Dictionary(Source):
        async def fetch(self, query: Query, config: SourceConfig) -> list[ContextChunk]:
            return [
                ContextChunk(content="OKR means objectives and key results", source=config.name)
            ]

    config = RouterConfig(
        sources={"glossary": SourceConfig(name="glossary", type="ux_test_dictionary")},
        routes=[RouteConfig(name="r", when="", sources=["glossary"])],
    )
    response = Router(config).query(Query(text="okr"))
    assert response.chunks


def test_unregistered_source_type_suggests_registering() -> None:
    config = RouterConfig(
        sources={"g": SourceConfig(name="g", type="redis")},
        routes=[RouteConfig(name="r", when="", sources=["g"])],
    )
    with pytest.raises(ConfigError, match="registered with @register_source"):
        Router(config)


@pytest.mark.parametrize(
    ("path", "pattern", "expected"),
    [
        ("confidential/salaries.txt", "**/confidential/**", True),
        ("hr/confidential/salaries.txt", "**/confidential/**", True),
        ("notconfidential/a.txt", "**/confidential/**", False),
        ("policy.md", "**/*.md", True),
        ("docs/a.md", "docs/**/*.md", True),
        ("docs/x/a.md", "docs/**/*.md", True),
        ("public/a.txt", "**/secrets/**", False),
    ],
)
def test_double_star_slash_matches_zero_folders(path: str, pattern: str, expected: bool) -> None:
    from theaios.context_router.paths import path_matches

    assert path_matches(path, pattern) is expected


def test_deny_paths_hide_a_top_level_folder(tmp_path: Path) -> None:
    from theaios.context_router.types import PermissionConfig, Query

    (tmp_path / "confidential").mkdir()
    (tmp_path / "confidential" / "salaries.txt").write_text("secret salary table")
    (tmp_path / "handbook.txt").write_text("welcome handbook")
    config = RouterConfig(
        sources={"docs": SourceConfig(name="docs", type="directory", path=str(tmp_path))},
        routes=[RouteConfig(name="r", when="", sources=["docs"])],
        permissions=[PermissionConfig(agent="intern", deny_paths=["**/confidential/**"])],
    )
    response = Router(config).query(Query(text="salary handbook", agent="intern"))
    texts = " ".join(c.content for c in response.chunks)
    assert "welcome handbook" in texts  # top-level file reached by the default **/*
    assert "secret salary table" not in texts


def test_condition_key_suggests_when(tmp_path: Path) -> None:
    errors = _errors(tmp_path, ROUTE.replace("when:", "condition:"))
    assert "unknown key 'condition' (did you mean 'when'?)" in errors


def test_query_metadata_cannot_override_agent_or_text() -> None:
    from theaios.context_router.types import Query

    config = RouterConfig(
        sources={"hr": SourceConfig(name="hr", type="inline", content="salary bands")},
        routes=[RouteConfig(name="hr-only", when='agent == "hr-bot"', sources=["hr"])],
    )
    router = Router(config)
    spoofed = router.query(Query(text="x", agent="intern", metadata={"agent": "hr-bot"}))
    assert spoofed.matched_routes == []
    assert router.query(Query(text="x", agent="hr-bot")).matched_routes == ["hr-only"]


def test_metadata_dot_key_in_route_conditions() -> None:
    from theaios.context_router.types import Query

    config = RouterConfig(
        variables={"dept": "finance"},
        sources={"fin": SourceConfig(name="fin", type="inline", content="ledger")},
        routes=[RouteConfig(name="fin", when="metadata.department == $dept", sources=["fin"])],
    )
    response = Router(config).query(Query(text="x", metadata={"department": "finance"}))
    assert response.matched_routes == ["fin"]


def test_cli_inspect_shows_brackets_verbatim(tmp_path: Path) -> None:
    from click.testing import CliRunner

    from theaios.context_router.cli import main

    path = tmp_path / "c.yaml"
    path.write_text(
        BASE
        + "routes:\n  - name: '[r]'\n    when: 'text contains \"[b]x[/b]\"'\n    sources: [docs]\n"
    )
    result = CliRunner().invoke(main, ["inspect", "--config", str(path)])
    assert "[r]" in result.output and "[b]x[/b]" in result.output
