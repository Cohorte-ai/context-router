"""Tests for shared data models and enums."""

from __future__ import annotations


from theaios.context_router.types import (
    VALID_DEFAULT_PERMISSIONS,
    VALID_RANKINGS,
    VALID_SOURCE_TYPES,
    VALID_TOKEN_ESTIMATORS,
    VALID_TRUNCATIONS,
    BudgetConfig,
    CacheConfig,
    ContextChunk,
    ContextResponse,
    DefaultPermission,
    PermissionConfig,
    Query,
    Ranking,
    RouteConfig,
    RouterConfig,
    RouterMetadata,
    SourceConfig,
    SourceType,
    TokenEstimator,
    Truncation,
)


class TestSourceType:
    """Tests for the SourceType enum."""

    def test_values(self) -> None:
        assert SourceType.INLINE.value == "inline"
        assert SourceType.DIRECTORY.value == "directory"
        assert SourceType.GIT_REPO.value == "git_repo"
        assert SourceType.HTTP_API.value == "http_api"

    def test_member_count(self) -> None:
        assert len(SourceType) == 4


class TestRanking:
    """Tests for the Ranking enum."""

    def test_values(self) -> None:
        assert Ranking.RELEVANCE.value == "relevance"
        assert Ranking.RECENCY.value == "recency"
        assert Ranking.MANUAL.value == "manual"

    def test_member_count(self) -> None:
        assert len(Ranking) == 3


class TestTruncation:
    """Tests for the Truncation enum."""

    def test_values(self) -> None:
        assert Truncation.DROP.value == "drop"
        assert Truncation.TRUNCATE_END.value == "truncate_end"
        assert Truncation.TRUNCATE_MIDDLE.value == "truncate_middle"

    def test_member_count(self) -> None:
        assert len(Truncation) == 3


class TestDefaultPermission:
    """Tests for the DefaultPermission enum."""

    def test_values(self) -> None:
        assert DefaultPermission.ALLOW.value == "allow"
        assert DefaultPermission.DENY.value == "deny"

    def test_member_count(self) -> None:
        assert len(DefaultPermission) == 2


class TestTokenEstimator:
    """Tests for the TokenEstimator enum."""

    def test_values(self) -> None:
        assert TokenEstimator.CHARS_DIV4.value == "chars_div4"
        assert TokenEstimator.WORDS.value == "words"
        assert TokenEstimator.WHITESPACE.value == "whitespace"

    def test_member_count(self) -> None:
        assert len(TokenEstimator) == 3


class TestValidSets:
    """Tests for the VALID_* constant sets."""

    def test_valid_source_types(self) -> None:
        assert VALID_SOURCE_TYPES == {"inline", "directory", "git_repo", "http_api"}

    def test_valid_rankings(self) -> None:
        assert VALID_RANKINGS == {"relevance", "recency", "manual", "embedding"}

    def test_valid_truncations(self) -> None:
        assert VALID_TRUNCATIONS == {"drop", "truncate_end", "truncate_middle"}

    def test_valid_default_permissions(self) -> None:
        assert VALID_DEFAULT_PERMISSIONS == {"allow", "deny"}

    def test_valid_token_estimators(self) -> None:
        assert VALID_TOKEN_ESTIMATORS == {"chars_div4", "words", "whitespace"}


class TestSourceConfig:
    """Tests for the SourceConfig dataclass."""

    def test_defaults(self) -> None:
        sc = SourceConfig(name="test", type="inline")
        assert sc.enabled is True
        assert sc.description == ""
        assert sc.path == ""
        assert sc.content == ""
        assert sc.url == ""
        assert sc.ref == "HEAD"
        assert sc.method == "GET"
        assert sc.headers == {}
        assert sc.body_template == ""
        assert sc.response_path == ""
        assert sc.result_text_field == "text"
        assert sc.result_title_field == "title"
        assert sc.patterns == ["**/*"]
        assert sc.exclude_patterns == []
        assert sc.recursive is True
        assert sc.encoding == "utf-8"
        assert sc.max_file_size == 1_000_000
        assert sc.tags == []
        assert sc.priority == 0

    def test_custom_values(self) -> None:
        sc = SourceConfig(
            name="api",
            type="http_api",
            url="https://example.com/api",
            method="POST",
            headers={"Authorization": "Bearer token"},
            priority=5,
            tags=["api", "external"],
        )
        assert sc.name == "api"
        assert sc.type == "http_api"
        assert sc.url == "https://example.com/api"
        assert sc.method == "POST"
        assert sc.headers == {"Authorization": "Bearer token"}
        assert sc.priority == 5
        assert sc.tags == ["api", "external"]


class TestRouteConfig:
    """Tests for the RouteConfig dataclass."""

    def test_defaults(self) -> None:
        rc = RouteConfig(name="test")
        assert rc.when == ""
        assert rc.sources == []
        assert rc.description == ""
        assert rc.enabled is True
        assert rc.tags == []

    def test_custom_values(self) -> None:
        rc = RouteConfig(
            name="policy-route",
            when='text contains "policy"',
            sources=["docs", "wiki"],
            description="Routes policy questions",
            tags=["policy"],
        )
        assert rc.name == "policy-route"
        assert rc.when == 'text contains "policy"'
        assert rc.sources == ["docs", "wiki"]


class TestPermissionConfig:
    """Tests for the PermissionConfig dataclass."""

    def test_defaults(self) -> None:
        pc = PermissionConfig()
        assert pc.agent == "*"
        assert pc.allow_sources == []
        assert pc.deny_sources == []
        assert pc.deny_paths == []
        assert pc.default == "allow"

    def test_custom_values(self) -> None:
        pc = PermissionConfig(
            agent="bot-a",
            allow_sources=["docs"],
            deny_sources=["secrets"],
            deny_paths=["**/internal/*"],
            default="deny",
        )
        assert pc.agent == "bot-a"
        assert pc.deny_sources == ["secrets"]


class TestBudgetConfig:
    """Tests for the BudgetConfig dataclass."""

    def test_defaults(self) -> None:
        bc = BudgetConfig()
        assert bc.max_tokens == 8000
        assert bc.ranking == "relevance"
        assert bc.truncation == "drop"
        assert bc.estimator == "chars_div4"
        assert bc.reserve_tokens == 0


class TestCacheConfig:
    """Tests for the CacheConfig dataclass."""

    def test_defaults(self) -> None:
        cc = CacheConfig()
        assert cc.enabled is False
        assert cc.directory == ".context-router-cache"
        assert cc.ttl == 300
        assert cc.max_entries == 1000


class TestRouterMetadata:
    """Tests for the RouterMetadata dataclass."""

    def test_defaults(self) -> None:
        rm = RouterMetadata()
        assert rm.name == ""
        assert rm.description == ""
        assert rm.author == ""


class TestRouterConfig:
    """Tests for the RouterConfig dataclass."""

    def test_defaults(self) -> None:
        rc = RouterConfig()
        assert rc.version == "1.0"
        assert isinstance(rc.metadata, RouterMetadata)
        assert rc.variables == {}
        assert rc.sources == {}
        assert rc.routes == []
        assert rc.permissions == []
        assert isinstance(rc.budget, BudgetConfig)
        assert isinstance(rc.cache, CacheConfig)


class TestQuery:
    """Tests for the Query dataclass."""

    def test_defaults(self) -> None:
        q = Query(text="hello")
        assert q.text == "hello"
        assert q.agent == "default"
        assert q.tags == []
        assert q.metadata == {}

    def test_custom_values(self) -> None:
        q = Query(
            text="find policies",
            agent="hr-bot",
            tags=["policy", "hr"],
            metadata={"department": "hr"},
        )
        assert q.agent == "hr-bot"
        assert q.tags == ["policy", "hr"]
        assert q.metadata["department"] == "hr"


class TestContextChunk:
    """Tests for the ContextChunk dataclass."""

    def test_defaults(self) -> None:
        cc = ContextChunk(content="hello", source="test")
        assert cc.content == "hello"
        assert cc.source == "test"
        assert cc.title == ""
        assert cc.path == ""
        assert cc.relevance_score == 0.0
        assert cc.token_count == 0
        assert cc.metadata == {}


class TestContextResponse:
    """Tests for the ContextResponse dataclass."""

    def test_defaults(self) -> None:
        cr = ContextResponse()
        assert cr.chunks == []
        assert cr.total_tokens == 0
        assert cr.was_truncated is False
        assert cr.matched_routes == []
        assert cr.denied_sources == []
        assert cr.evaluation_time_ms == 0.0
        assert cr.metadata == {}

    def test_is_empty_true(self) -> None:
        cr = ContextResponse()
        assert cr.is_empty is True

    def test_is_empty_false(self) -> None:
        cr = ContextResponse(chunks=[ContextChunk(content="hello", source="test")])
        assert cr.is_empty is False

    def test_text_property_single_chunk(self) -> None:
        cr = ContextResponse(chunks=[ContextChunk(content="hello world", source="test")])
        assert cr.text == "hello world"

    def test_text_property_multiple_chunks(self) -> None:
        cr = ContextResponse(
            chunks=[
                ContextChunk(content="first chunk", source="a"),
                ContextChunk(content="second chunk", source="b"),
            ]
        )
        assert cr.text == "first chunk\n\nsecond chunk"

    def test_text_property_empty(self) -> None:
        cr = ContextResponse()
        assert cr.text == ""
