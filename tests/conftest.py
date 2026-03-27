"""Shared fixtures for theaios-context-router tests."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from theaios.context_router.types import (
    BudgetConfig,
    CacheConfig,
    PermissionConfig,
    Query,
    RouteConfig,
    RouterConfig,
    RouterMetadata,
    SourceConfig,
)


@pytest.fixture()
def tmp_dir(tmp_path: Path) -> Path:
    """Return a temporary directory for test file I/O."""
    return tmp_path


@pytest.fixture()
def basic_config(tmp_path: Path) -> RouterConfig:
    """Minimal RouterConfig with inline + directory sources."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "hello.txt").write_text("Hello from the data directory.", encoding="utf-8")
    (data_dir / "guide.md").write_text(
        textwrap.dedent("""\
            # Guide

            ## Getting Started

            Welcome to the getting started section.

            ## Advanced Usage

            This is the advanced usage section.
        """),
        encoding="utf-8",
    )

    return RouterConfig(
        version="1.0",
        metadata=RouterMetadata(name="test-router", description="Test configuration"),
        sources={
            "instructions": SourceConfig(
                name="instructions",
                type="inline",
                content="You are a helpful assistant. Be concise.",
            ),
            "docs": SourceConfig(
                name="docs",
                type="directory",
                path=str(data_dir),
                patterns=["**/*"],
            ),
        },
        routes=[
            RouteConfig(
                name="default",
                when="",
                sources=["instructions", "docs"],
            ),
            RouteConfig(
                name="help-queries",
                when='text contains "help"',
                sources=["docs"],
            ),
        ],
        permissions=[
            PermissionConfig(
                agent="*",
                default="allow",
            ),
        ],
        budget=BudgetConfig(max_tokens=4000, ranking="relevance", truncation="drop"),
        cache=CacheConfig(enabled=False),
    )


@pytest.fixture()
def basic_yaml(tmp_path: Path) -> Path:
    """Write a valid context-router.yaml and return its path."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "notes.txt").write_text("Some notes content here.", encoding="utf-8")
    (data_dir / "readme.md").write_text(
        textwrap.dedent("""\
            # README

            ## Installation

            Run pip install to get started.

            ## Usage

            Import the library and call query().
        """),
        encoding="utf-8",
    )

    yaml_content = textwrap.dedent(f"""\
        version: "1.0"

        metadata:
          name: test-config
          description: A test configuration
          author: tester

        sources:
          system_prompt:
            type: inline
            content: "You are a helpful assistant."
            priority: 10

          local_docs:
            type: directory
            path: "{data_dir}"
            patterns:
              - "**/*.md"
              - "**/*.txt"
            exclude_patterns:
              - "**/.DS_Store"
            max_file_size: 500000

        routes:
          - name: default
            when: ""
            sources:
              - system_prompt
              - local_docs

          - name: docs-only
            when: 'text contains "documentation"'
            sources:
              - local_docs

        permissions:
          - agent: "*"
            default: allow

          - agent: restricted-bot
            deny_sources:
              - local_docs
            default: deny

        budget:
          max_tokens: 4000
          ranking: relevance
          truncation: drop
          estimator: chars_div4
          reserve_tokens: 200

        cache:
          enabled: false
          ttl: 300
          max_entries: 100
    """)

    config_path = tmp_path / "context-router.yaml"
    config_path.write_text(yaml_content, encoding="utf-8")
    return config_path


@pytest.fixture()
def sample_data_dir(tmp_path: Path) -> Path:
    """Create a temp directory with sample .md and .txt files."""
    data_dir = tmp_path / "sample_data"
    data_dir.mkdir()

    # Plain text file
    (data_dir / "notes.txt").write_text(
        "Meeting notes from the weekly standup. Discussed project timeline.",
        encoding="utf-8",
    )

    # Markdown with H2 sections
    (data_dir / "policy.md").write_text(
        textwrap.dedent("""\
            # Company Policy

            ## Remote Work

            Employees may work remotely up to 3 days per week.
            A VPN connection is required for all remote access.

            ## Travel

            All travel must be approved by your manager.
            Economy class for domestic, business for international over 6 hours.
        """),
        encoding="utf-8",
    )

    # Another plain text file
    (data_dir / "faq.txt").write_text(
        "Q: What is the vacation policy?\nA: Full-time employees get 20 days PTO per year.",
        encoding="utf-8",
    )

    # A subdirectory with files
    sub = data_dir / "archive"
    sub.mkdir()
    (sub / "old_notes.txt").write_text(
        "These are archived notes from last quarter.", encoding="utf-8"
    )

    # A file that should be excluded
    (data_dir / ".DS_Store").write_text("binary junk", encoding="utf-8")

    return data_dir


@pytest.fixture()
def sample_query() -> Query:
    """A basic Query for testing."""
    return Query(
        text="What is the remote work policy?",
        agent="test-agent",
        tags=["policy"],
        metadata={"department": "engineering"},
    )
