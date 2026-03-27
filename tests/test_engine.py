"""Tests for the Context Router engine (main routing pipeline)."""

from __future__ import annotations


from theaios.context_router.engine import Router
from theaios.context_router.types import (
    BudgetConfig,
    CacheConfig,
    ContextResponse,
    PermissionConfig,
    Query,
    RouteConfig,
    RouterConfig,
    SourceConfig,
)


class TestRouter:
    """Tests for Router.query() — the full routing pipeline."""

    def test_query_with_route_matching(self, basic_config: RouterConfig) -> None:
        router = Router(basic_config)
        q = Query(text="I need help with something")
        response = router.query(q)

        assert isinstance(response, ContextResponse)
        # "help-queries" route should match (text contains "help")
        assert "help-queries" in response.matched_routes
        assert not response.is_empty

    def test_query_with_default_route(self, basic_config: RouterConfig) -> None:
        router = Router(basic_config)
        q = Query(text="anything at all")
        response = router.query(q)

        # Default route (empty when = always true) should match
        assert "default" in response.matched_routes
        assert not response.is_empty

    def test_query_returns_chunks_from_sources(self, basic_config: RouterConfig) -> None:
        router = Router(basic_config)
        q = Query(text="tell me something")
        response = router.query(q)

        sources_in_response = {c.source for c in response.chunks}
        # Default route includes both "instructions" and "docs"
        assert "instructions" in sources_in_response or "docs" in sources_in_response

    def test_permission_filtering_denied_sources_not_queried(self) -> None:
        config = RouterConfig(
            sources={
                "public": SourceConfig(
                    name="public",
                    type="inline",
                    content="Public info available to everyone.",
                ),
                "secret": SourceConfig(
                    name="secret",
                    type="inline",
                    content="Top secret classified information.",
                ),
            },
            routes=[
                RouteConfig(name="all", when="", sources=["public", "secret"]),
            ],
            permissions=[
                PermissionConfig(
                    agent="limited-bot",
                    deny_sources=["secret"],
                    default="allow",
                ),
            ],
            cache=CacheConfig(enabled=False),
        )
        router = Router(config)
        q = Query(text="tell me everything", agent="limited-bot")
        response = router.query(q)

        # Secret should be denied
        assert "secret" in response.denied_sources

        # Only public content should be in chunks
        sources_in_response = {c.source for c in response.chunks}
        assert "public" in sources_in_response
        assert "secret" not in sources_in_response

    def test_path_filtering_deny_paths_applied(self) -> None:
        config = RouterConfig(
            sources={
                "public": SourceConfig(
                    name="public",
                    type="inline",
                    content="Public data.",
                ),
            },
            routes=[
                RouteConfig(name="all", when="", sources=["public"]),
            ],
            permissions=[
                PermissionConfig(
                    agent="test-agent",
                    deny_paths=["**/secret/*"],
                    default="allow",
                ),
            ],
            cache=CacheConfig(enabled=False),
        )
        router = Router(config)
        q = Query(text="anything", agent="test-agent")
        response = router.query(q)

        # Inline source has no path, so deny_paths won't filter it
        assert not response.is_empty

    def test_budget_enforcement(self) -> None:
        config = RouterConfig(
            sources={
                "big": SourceConfig(
                    name="big",
                    type="inline",
                    content="x" * 10000,  # Very large content
                ),
                "small": SourceConfig(
                    name="small",
                    type="inline",
                    content="Small content.",
                ),
            },
            routes=[
                RouteConfig(name="all", when="", sources=["big", "small"]),
            ],
            budget=BudgetConfig(max_tokens=50, truncation="drop"),
            cache=CacheConfig(enabled=False),
        )
        router = Router(config)
        q = Query(text="test")
        response = router.query(q)

        # Budget is very small, so the big chunk should be dropped
        assert response.total_tokens <= 50

    def test_empty_response_when_all_denied(self) -> None:
        config = RouterConfig(
            sources={
                "docs": SourceConfig(
                    name="docs",
                    type="inline",
                    content="Some docs.",
                ),
            },
            routes=[
                RouteConfig(name="all", when="", sources=["docs"]),
            ],
            permissions=[
                PermissionConfig(
                    agent="blocked-bot",
                    deny_sources=["docs"],
                    default="deny",
                ),
            ],
            cache=CacheConfig(enabled=False),
        )
        router = Router(config)
        q = Query(text="anything", agent="blocked-bot")
        response = router.query(q)

        assert response.is_empty
        assert "docs" in response.denied_sources

    def test_no_routes_match_returns_empty(self) -> None:
        config = RouterConfig(
            sources={
                "docs": SourceConfig(
                    name="docs",
                    type="inline",
                    content="Some docs.",
                ),
            },
            routes=[
                RouteConfig(
                    name="specific",
                    when='text contains "very-specific-keyword-xyz"',
                    sources=["docs"],
                ),
            ],
            cache=CacheConfig(enabled=False),
        )
        router = Router(config)
        q = Query(text="generic query")
        response = router.query(q)

        assert response.is_empty
        assert response.matched_routes == []

    def test_evaluation_time_is_set(self, basic_config: RouterConfig) -> None:
        router = Router(basic_config)
        q = Query(text="test")
        response = router.query(q)
        assert response.evaluation_time_ms > 0

    def test_disabled_route_not_evaluated(self) -> None:
        config = RouterConfig(
            sources={
                "docs": SourceConfig(
                    name="docs",
                    type="inline",
                    content="Some content.",
                ),
            },
            routes=[
                RouteConfig(
                    name="disabled-route",
                    when="",
                    sources=["docs"],
                    enabled=False,
                ),
            ],
            cache=CacheConfig(enabled=False),
        )
        router = Router(config)
        q = Query(text="test")
        response = router.query(q)

        # Disabled route should not be matched
        assert "disabled-route" not in response.matched_routes
        assert response.is_empty

    def test_disabled_source_not_fetched(self) -> None:
        config = RouterConfig(
            sources={
                "active": SourceConfig(
                    name="active",
                    type="inline",
                    content="Active source.",
                    enabled=True,
                ),
                "inactive": SourceConfig(
                    name="inactive",
                    type="inline",
                    content="Inactive source.",
                    enabled=False,
                ),
            },
            routes=[
                RouteConfig(name="all", when="", sources=["active", "inactive"]),
            ],
            cache=CacheConfig(enabled=False),
        )
        router = Router(config)
        q = Query(text="test")
        response = router.query(q)

        sources_in_response = {c.source for c in response.chunks}
        assert "active" in sources_in_response
        assert "inactive" not in sources_in_response

    def test_multiple_routes_merge_sources(self) -> None:
        config = RouterConfig(
            sources={
                "docs": SourceConfig(
                    name="docs",
                    type="inline",
                    content="Documentation content.",
                ),
                "faq": SourceConfig(
                    name="faq",
                    type="inline",
                    content="FAQ answers here.",
                ),
            },
            routes=[
                RouteConfig(name="route-a", when="", sources=["docs"]),
                RouteConfig(name="route-b", when="", sources=["faq"]),
            ],
            cache=CacheConfig(enabled=False),
        )
        router = Router(config)
        q = Query(text="test")
        response = router.query(q)

        assert "route-a" in response.matched_routes
        assert "route-b" in response.matched_routes

        sources_in_response = {c.source for c in response.chunks}
        assert "docs" in sources_in_response
        assert "faq" in sources_in_response

    def test_config_property(self, basic_config: RouterConfig) -> None:
        router = Router(basic_config)
        assert router.config is basic_config

    def test_cache_property(self, basic_config: RouterConfig) -> None:
        router = Router(basic_config)
        assert router.cache is not None
