"""End-to-end integration tests for the full context routing pipeline."""

from __future__ import annotations

import textwrap
from pathlib import Path


from theaios.context_router.config import load_config
from theaios.context_router.engine import Router
from theaios.context_router.types import Query


class TestEndToEnd:
    """Full pipeline: write YAML + data files, load config, query, verify response."""

    def test_full_pipeline_inline_and_directory(self, tmp_path: Path) -> None:
        # Create data files
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        (data_dir / "policy.md").write_text(
            textwrap.dedent("""\
                # Policies

                ## Remote Work

                Employees may work remotely up to 3 days per week.
                Manager approval is required for full-time remote work.

                ## Expenses

                All expenses over $500 require VP approval.
                Receipts must be submitted within 30 days.
            """),
            encoding="utf-8",
        )
        (data_dir / "faq.txt").write_text(
            "Q: What is the PTO policy? A: 20 days per year for full-time employees.",
            encoding="utf-8",
        )

        # Write YAML config
        yaml_content = textwrap.dedent(f"""\
            version: "1.0"

            metadata:
              name: e2e-test
              description: End-to-end test configuration

            sources:
              system_prompt:
                type: inline
                content: "You are an HR assistant. Answer questions about company policies."
                priority: 10

              policies:
                type: directory
                path: "{data_dir}"
                patterns:
                  - "*.md"
                  - "*.txt"
                  - "**/*.md"
                  - "**/*.txt"

            routes:
              - name: default
                when: ""
                sources:
                  - system_prompt
                  - policies

              - name: policy-questions
                when: 'text contains "policy"'
                sources:
                  - policies

            permissions:
              - agent: "*"
                default: allow

              - agent: external-bot
                deny_sources:
                  - policies
                default: deny

            budget:
              max_tokens: 4000
              ranking: relevance
              truncation: drop
              estimator: chars_div4
        """)

        config_path = tmp_path / "context-router.yaml"
        config_path.write_text(yaml_content, encoding="utf-8")

        # Load config
        config = load_config(str(config_path))
        assert config.metadata.name == "e2e-test"
        assert len(config.sources) == 2
        assert len(config.routes) == 2

        # Create router
        router = Router(config)

        # Query as default agent
        q = Query(text="What is the remote work policy?", agent="hr-agent")
        response = router.query(q)

        assert not response.is_empty
        assert response.total_tokens > 0
        assert response.evaluation_time_ms > 0
        assert len(response.matched_routes) > 0

        # Check that we got relevant content
        full_text = response.text.lower()
        assert "remote" in full_text or "work" in full_text

        # Query as external bot (should be denied)
        q_denied = Query(text="What is the remote work policy?", agent="external-bot")
        response_denied = router.query(q_denied)

        assert "policies" in response_denied.denied_sources

    def test_route_condition_matching(self, tmp_path: Path) -> None:
        yaml_content = textwrap.dedent("""\
            version: "1.0"

            sources:
              general:
                type: inline
                content: "General information for all queries."

              technical:
                type: inline
                content: "Technical documentation about APIs and architecture."

              hr_info:
                type: inline
                content: "Human resources policies and procedures."

            routes:
              - name: tech-questions
                when: 'text contains "api" or text contains "technical"'
                sources:
                  - technical

              - name: hr-questions
                when: 'text contains "hr" or text contains "policy"'
                sources:
                  - hr_info

              - name: fallback
                when: ""
                sources:
                  - general
        """)

        config_path = tmp_path / "context-router.yaml"
        config_path.write_text(yaml_content, encoding="utf-8")

        config = load_config(str(config_path))
        router = Router(config)

        # Technical query
        tech_response = router.query(Query(text="How does the api work?"))
        assert "tech-questions" in tech_response.matched_routes
        assert any("Technical" in c.content or "API" in c.content for c in tech_response.chunks)

        # HR query
        hr_response = router.query(Query(text="What is the hr policy?"))
        assert "hr-questions" in hr_response.matched_routes

        # General query (only fallback matches)
        general_response = router.query(Query(text="Hello there"))
        assert "fallback" in general_response.matched_routes

    def test_budget_limits_output(self, tmp_path: Path) -> None:
        yaml_content = textwrap.dedent("""\
            version: "1.0"

            sources:
              large:
                type: inline
                content: "{content}"

              small:
                type: inline
                content: "Small snippet."

            routes:
              - name: all
                when: ""
                sources:
                  - large
                  - small

            budget:
              max_tokens: 20
              ranking: relevance
              truncation: drop
        """).format(content="x" * 1000)

        config_path = tmp_path / "context-router.yaml"
        config_path.write_text(yaml_content, encoding="utf-8")

        config = load_config(str(config_path))
        router = Router(config)

        response = router.query(Query(text="test"))
        assert response.total_tokens <= 20

    def test_multiple_agents_different_permissions(self, tmp_path: Path) -> None:
        yaml_content = textwrap.dedent("""\
            version: "1.0"

            sources:
              public:
                type: inline
                content: "Public information available to everyone."

              internal:
                type: inline
                content: "Internal company data - restricted access."

              confidential:
                type: inline
                content: "Confidential financial reports."

            routes:
              - name: all
                when: ""
                sources:
                  - public
                  - internal
                  - confidential

            permissions:
              - agent: "*"
                default: allow

              - agent: public-bot
                allow_sources:
                  - public
                default: deny

              - agent: internal-bot
                deny_sources:
                  - confidential
                default: allow
        """)

        config_path = tmp_path / "context-router.yaml"
        config_path.write_text(yaml_content, encoding="utf-8")

        config = load_config(str(config_path))
        router = Router(config)

        # Admin sees everything
        admin_response = router.query(Query(text="show all", agent="admin"))
        admin_sources = {c.source for c in admin_response.chunks}
        assert "public" in admin_sources
        assert "internal" in admin_sources
        assert "confidential" in admin_sources

        # Public bot only sees public
        public_response = router.query(Query(text="show all", agent="public-bot"))
        public_sources = {c.source for c in public_response.chunks}
        assert "public" in public_sources
        assert "internal" not in public_sources
        assert "confidential" not in public_sources

        # Internal bot sees public + internal but not confidential
        internal_response = router.query(Query(text="show all", agent="internal-bot"))
        internal_sources = {c.source for c in internal_response.chunks}
        assert "public" in internal_sources
        assert "internal" in internal_sources
        assert "confidential" not in internal_sources
