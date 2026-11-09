"""YAML configuration loader and validation."""

from __future__ import annotations

import difflib
from collections.abc import Iterable
from pathlib import Path

import yaml
from theaios.core.expressions import ExpressionError, compile_expression, references
from theaios.core.env import interpolate_env, interpolate_recursive

from theaios.context_router.types import (
    VALID_DEFAULT_PERMISSIONS,
    VALID_RANKINGS,
    VALID_SOURCE_TYPES,
    VALID_TOKEN_ESTIMATORS,
    VALID_TRUNCATIONS,
    BudgetConfig,
    CacheConfig,
    EmbeddingConfig,
    PermissionConfig,
    RouteConfig,
    RouterConfig,
    RouterMetadata,
    SourceConfig,
)


class ConfigError(Exception):
    """Raised when a configuration file is invalid."""

    def __init__(self, errors: list[str]) -> None:
        self.errors = errors
        super().__init__("Invalid config:\n  " + "\n  ".join(errors))


# ---------------------------------------------------------------------------
# Environment variable interpolation
# ---------------------------------------------------------------------------


def _interpolate_env(value: str) -> str:
    """Replace ${VAR} placeholders (see theaios.core.env)."""
    return interpolate_env(value, strict_names=True)


def _interpolate_recursive(obj: object) -> object:
    """Interpolate env vars in every string of a parsed config."""
    return interpolate_recursive(obj, strict_names=True)


def load_config(path: str = "context-router.yaml") -> RouterConfig:
    """Load a YAML config file, validate, and return typed config."""
    config_path = Path(path)
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    with open(config_path) as f:
        raw = yaml.safe_load(f)

    if not isinstance(raw, dict):
        raise ConfigError(["Config file must be a YAML mapping"])

    # Security: parse and validate YAML structure BEFORE interpolating env vars.
    # This ensures that malformed configs are rejected before any env var values
    # are substituted, preventing env var contents from leaking in error messages.
    config = _parse_config(raw)

    # Now interpolate env vars on the raw dict and re-parse
    raw = _interpolate_recursive(raw)
    if not isinstance(raw, dict):
        raise ConfigError(["Config file must be a YAML mapping after interpolation"])

    config = _parse_config(raw)

    errors = validate_config(config)
    if errors:
        raise ConfigError(errors)

    return config


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------


def _parse_config(raw: dict[str, object]) -> RouterConfig:
    """Parse raw YAML dict into typed RouterConfig."""

    # Version
    version = str(raw.get("version", "1.0"))

    # Metadata
    meta_raw = raw.get("metadata", {})
    if not isinstance(meta_raw, dict):
        meta_raw = {}
    metadata = RouterMetadata(
        name=str(meta_raw.get("name", "")),
        description=str(meta_raw.get("description", "")),
        author=str(meta_raw.get("author", "")),
    )

    # Variables
    variables_raw = raw.get("variables", {})
    variables: dict[str, object] = dict(variables_raw) if isinstance(variables_raw, dict) else {}

    # Sources
    sources: dict[str, SourceConfig] = {}
    sources_raw = raw.get("sources", {})
    if isinstance(sources_raw, dict):
        for name, sraw in sources_raw.items():
            if not isinstance(sraw, dict):
                sraw = {}
            str_name = str(name)

            headers_raw = sraw.get("headers", {})
            headers = (
                {str(k): str(v) for k, v in headers_raw.items()}
                if isinstance(headers_raw, dict)
                else {}
            )

            patterns_raw = sraw.get("patterns", ["**/*"])
            patterns = (
                [str(p) for p in patterns_raw] if isinstance(patterns_raw, list) else ["**/*"]
            )

            exclude_raw = sraw.get("exclude_patterns", [])
            exclude = [str(p) for p in exclude_raw] if isinstance(exclude_raw, list) else []

            tags_raw = sraw.get("tags", [])
            tags = [str(t) for t in tags_raw] if isinstance(tags_raw, list) else []

            sources[str_name] = SourceConfig(
                name=str_name,
                type=str(sraw.get("type", "")),
                enabled=bool(sraw.get("enabled", True)),
                description=str(sraw.get("description", "")),
                path=str(sraw.get("path", "")),
                content=str(sraw.get("content", "")),
                url=str(sraw.get("url", "")),
                ref=str(sraw.get("ref", "HEAD")),
                method=str(sraw.get("method", "GET")),
                headers=headers,
                body_template=str(sraw.get("body_template", "")),
                response_path=str(sraw.get("response_path", "")),
                result_text_field=str(sraw.get("result_text_field", "text")),
                result_title_field=str(sraw.get("result_title_field", "title")),
                patterns=patterns,
                exclude_patterns=exclude,
                recursive=bool(sraw.get("recursive", True)),
                encoding=str(sraw.get("encoding", "utf-8")),
                max_file_size=int(sraw.get("max_file_size", 1_000_000)),
                tags=tags,
                priority=int(sraw.get("priority", 0)),
            )

    # Routes
    routes: list[RouteConfig] = []
    routes_raw = raw.get("routes", [])
    if isinstance(routes_raw, list):
        for rraw in routes_raw:
            if not isinstance(rraw, dict):
                continue

            route_sources_raw = rraw.get("sources", [])
            route_sources = (
                [str(s) for s in route_sources_raw] if isinstance(route_sources_raw, list) else []
            )

            tags_raw = rraw.get("tags", [])
            tags = [str(t) for t in tags_raw] if isinstance(tags_raw, list) else []

            routes.append(
                RouteConfig(
                    name=str(rraw.get("name", "")),
                    when=str(rraw.get("when", "")),
                    sources=route_sources,
                    description=str(rraw.get("description", "")),
                    enabled=bool(rraw.get("enabled", True)),
                    tags=tags,
                )
            )

    # Permissions
    permissions: list[PermissionConfig] = []
    permissions_raw = raw.get("permissions", [])
    if isinstance(permissions_raw, list):
        for praw in permissions_raw:
            if not isinstance(praw, dict):
                continue

            allow_raw = praw.get("allow_sources", [])
            allow = [str(s) for s in allow_raw] if isinstance(allow_raw, list) else []

            deny_raw = praw.get("deny_sources", [])
            deny = [str(s) for s in deny_raw] if isinstance(deny_raw, list) else []

            deny_paths_raw = praw.get("deny_paths", [])
            deny_paths = (
                [str(p) for p in deny_paths_raw] if isinstance(deny_paths_raw, list) else []
            )

            permissions.append(
                PermissionConfig(
                    agent=str(praw.get("agent", "*")),
                    allow_sources=allow,
                    deny_sources=deny,
                    deny_paths=deny_paths,
                    default=str(praw.get("default", "allow")),
                )
            )

    # Budget
    budget_raw = raw.get("budget", {})
    if not isinstance(budget_raw, dict):
        budget_raw = {}
    embedding_config: EmbeddingConfig | None = None
    emb_raw = budget_raw.get("embedding")
    if isinstance(emb_raw, dict):
        embedding_config = EmbeddingConfig(
            model=str(emb_raw.get("model", "text-embedding-3-small")),
            api_key_env=str(emb_raw.get("api_key_env", "OPENAI_API_KEY")),
            url=str(emb_raw.get("url", "https://api.openai.com/v1/embeddings")),
            cache_dir=str(emb_raw.get("cache_dir", ".context_router_embeddings")),
        )

    budget = BudgetConfig(
        max_tokens=int(budget_raw.get("max_tokens", 8000)),
        ranking=str(budget_raw.get("ranking", "relevance")),
        truncation=str(budget_raw.get("truncation", "drop")),
        estimator=str(budget_raw.get("estimator", "chars_div4")),
        reserve_tokens=int(budget_raw.get("reserve_tokens", 0)),
        embedding=embedding_config,
    )

    # Cache
    cache_raw = raw.get("cache", {})
    if not isinstance(cache_raw, dict):
        cache_raw = {}
    cache = CacheConfig(
        enabled=bool(cache_raw.get("enabled", False)),
        directory=str(cache_raw.get("directory", ".context-router-cache")),
        ttl=int(cache_raw.get("ttl", 300)),
        max_entries=int(cache_raw.get("max_entries", 1000)),
    )

    return RouterConfig(
        version=version,
        metadata=metadata,
        variables=variables,
        sources=sources,
        routes=routes,
        permissions=permissions,
        budget=budget,
        cache=cache,
    )


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def _did_you_mean(name: str, known: Iterable[str]) -> str:
    close = difflib.get_close_matches(name, list(known), n=1)
    return f" (did you mean '{close[0]}'?)" if close else ""


def when_errors(when: str, variables: Iterable[str]) -> list[str]:
    """Problems in a route's ``when``: a syntax error, an undefined ``$variable``, or
    ``matches`` (context-router has no matchers). Each would make the route never match."""
    try:
        refs = references(compile_expression(when))
    except ExpressionError as exc:
        return [f"invalid 'when': {exc}"]
    known = set(variables)
    errors = [
        f"'when' uses undefined variable '${name}'{_did_you_mean(name, known)}"
        for name in sorted(refs.variables - known)
    ]
    errors += [
        f"'when' uses 'matches {name}', but context-router has no matchers"
        for name in sorted(refs.matchers)
    ]
    return errors


def validate_config(config: RouterConfig) -> list[str]:
    """Return list of validation errors (empty = valid)."""
    errors: list[str] = []

    # Version
    if config.version not in ("1.0",):
        errors.append(f"Unsupported config version: '{config.version}' (expected '1.0')")

    # Sources
    for name, source in config.sources.items():
        prefix = f"sources.{name}"

        if not source.type:
            errors.append(f"{prefix}: 'type' is required")
        elif source.type not in VALID_SOURCE_TYPES:
            errors.append(
                f"{prefix}: invalid type '{source.type}', "
                f"expected one of {sorted(VALID_SOURCE_TYPES)}"
            )

        if source.type == "inline" and not source.content:
            errors.append(f"{prefix}: inline source requires 'content'")

        if source.type == "directory" and not source.path:
            errors.append(f"{prefix}: directory source requires 'path'")

        if source.type == "git_repo" and not source.path:
            errors.append(f"{prefix}: git_repo source requires 'path'")

        if source.type == "http_api" and not source.url:
            errors.append(f"{prefix}: http_api source requires 'url'")

    # Routes
    seen_names: set[str] = set()
    source_names = set(config.sources.keys())
    for i, route in enumerate(config.routes):
        prefix = f"routes[{i}]"

        if not route.name:
            errors.append(f"{prefix}: 'name' is required")
        elif route.name in seen_names:
            errors.append(f"{prefix}: duplicate route name '{route.name}'")
        else:
            seen_names.add(route.name)

        if not route.sources:
            errors.append(f"{prefix} ({route.name}): at least one source is required")

        if route.enabled:
            errors.extend(
                f"{prefix} ({route.name}): {e}" for e in when_errors(route.when, config.variables)
            )

        for sname in route.sources:
            if sname not in source_names:
                errors.append(f"{prefix} ({route.name}): source '{sname}' is not defined")

    # Permissions
    for i, perm in enumerate(config.permissions):
        prefix = f"permissions[{i}]"

        if perm.default not in VALID_DEFAULT_PERMISSIONS:
            errors.append(
                f"{prefix}: invalid default '{perm.default}', "
                f"expected one of {sorted(VALID_DEFAULT_PERMISSIONS)}"
            )

        for sname in perm.allow_sources:
            if sname not in source_names:
                errors.append(f"{prefix}: allow_sources reference '{sname}' is not defined")

        for sname in perm.deny_sources:
            if sname not in source_names:
                errors.append(f"{prefix}: deny_sources reference '{sname}' is not defined")

    # Budget
    if config.budget.max_tokens < 1:
        errors.append("budget.max_tokens must be >= 1")

    if config.budget.ranking not in VALID_RANKINGS:
        errors.append(
            f"budget.ranking: invalid value '{config.budget.ranking}', "
            f"expected one of {sorted(VALID_RANKINGS)}"
        )

    if config.budget.truncation not in VALID_TRUNCATIONS:
        errors.append(
            f"budget.truncation: invalid value '{config.budget.truncation}', "
            f"expected one of {sorted(VALID_TRUNCATIONS)}"
        )

    if config.budget.estimator not in VALID_TOKEN_ESTIMATORS:
        errors.append(
            f"budget.estimator: invalid value '{config.budget.estimator}', "
            f"expected one of {sorted(VALID_TOKEN_ESTIMATORS)}"
        )

    if config.budget.reserve_tokens < 0:
        errors.append("budget.reserve_tokens must be >= 0")

    # Cache
    if config.cache.ttl < 0:
        errors.append("cache.ttl must be >= 0")

    if config.cache.max_entries < 1:
        errors.append("cache.max_entries must be >= 1")

    return errors
