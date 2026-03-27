"""Permissions example — different agents see different context."""

from __future__ import annotations

import os
from pathlib import Path

from theaios.context_router import Query, Router, load_config

os.chdir(Path(__file__).parent)
config = load_config("configs/basic.yaml")
router = Router(config)

query_text = "What is the remote work policy?"

# Agent with full access
response = router.query(Query(text=query_text, agent="default"))
print(f"default agent:    {len(response.chunks)} chunks, {response.total_tokens} tokens")
print(f"  Denied sources: {response.denied_sources or 'none'}")

# Simulate a restricted agent — let's build a config with permissions
from theaios.context_router.types import (
    BudgetConfig,
    PermissionConfig,
    RouteConfig,
    RouterConfig,
    SourceConfig,
)

restricted_config = RouterConfig(
    sources={
        "policies": SourceConfig(name="policies", type="directory", path="./data/policies"),
        "projects": SourceConfig(name="projects", type="directory", path="./data/projects"),
    },
    routes=[RouteConfig(name="default", sources=["policies", "projects"])],
    permissions=[
        PermissionConfig(
            agent="hr-agent",
            allow_sources=["policies"],
            deny_sources=["projects"],
            default="deny",
        ),
    ],
    budget=BudgetConfig(),
)
restricted_router = Router(restricted_config)

# HR agent — can see policies, not projects
response = restricted_router.query(Query(text="Tell me about project atlas", agent="hr-agent"))
print(f"\nhr-agent:         {len(response.chunks)} chunks, {response.total_tokens} tokens")
print(f"  Denied sources: {response.denied_sources}")

# Unknown agent — denied by default
response = restricted_router.query(Query(text="Anything", agent="unknown-agent"))
print(f"\nunknown-agent:    {len(response.chunks)} chunks (default: deny)")
print(f"  Denied sources: {response.denied_sources}")
