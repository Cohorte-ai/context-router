"""A typo in a route's `when` must be caught at load, not turn the route off silently."""

from __future__ import annotations

from pathlib import Path

import pytest

from theaios.context_router.config import ConfigError, load_config, validate_config
from theaios.context_router.engine import Router
from theaios.context_router.types import RouteConfig, RouterConfig, SourceConfig

CONFIG = """
version: "1.0"
variables:
  engineering_teams: [platform, backend]
sources:
  eng_docs:
    type: inline
    content: "Engineering handbook"
routes:
  - name: engineering
    when: "agent in $engineering_team"
    sources: [eng_docs]
  - name: injection
    when: "text matches prompt_injection"
    sources: [eng_docs]
"""


def _config(when: str, enabled: bool = True) -> RouterConfig:
    return RouterConfig(
        variables={"engineering_teams": ["platform"]},
        sources={"eng_docs": SourceConfig(name="eng_docs", type="inline", content="x")},
        routes=[RouteConfig(name="r", when=when, sources=["eng_docs"], enabled=enabled)],
    )


def test_load_rejects_undefined_variable_and_matches(tmp_path: Path) -> None:
    path = tmp_path / "context-router.yaml"
    path.write_text(CONFIG)
    with pytest.raises(ConfigError) as exc:
        load_config(str(path))
    errors = "\n".join(exc.value.errors)
    assert "undefined variable '$engineering_team' (did you mean 'engineering_teams'?)" in errors
    assert "'matches prompt_injection', but context-router has no matchers" in errors


def test_router_built_in_code_rejects_undefined_variable() -> None:
    with pytest.raises(ConfigError, match="engineering_team"):
        Router(_config("agent in $engineering_team"))


def test_disabled_route_is_not_checked() -> None:
    assert validate_config(_config("agent in $nope", enabled=False)) == []


def test_correct_route_still_validates() -> None:
    assert validate_config(_config("agent in $engineering_teams")) == []
    Router(_config("agent in $engineering_teams"))
