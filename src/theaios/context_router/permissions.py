"""Permission resolution and filtering for context sources."""

from __future__ import annotations

import fnmatch
from dataclasses import dataclass, field

from theaios.context_router.types import ContextChunk, PermissionConfig, SourceConfig


# ---------------------------------------------------------------------------
# Resolved permission
# ---------------------------------------------------------------------------


@dataclass
class ResolvedPermission:
    """The resolved permission state for a specific agent."""

    agent: str
    allowed_sources: set[str] = field(default_factory=set)
    denied_sources: set[str] = field(default_factory=set)
    deny_paths: list[str] = field(default_factory=list)
    default: str = "allow"


# ---------------------------------------------------------------------------
# Resolution
# ---------------------------------------------------------------------------


def resolve_permission(
    agent: str,
    permissions: list[PermissionConfig],
) -> ResolvedPermission:
    """Resolve the effective permission for an agent.

    Permission rules are evaluated in order. More specific agent matches
    (exact name) take precedence over wildcards ("*"). If multiple rules
    match, they are merged: deny lists are unioned, allow lists are unioned,
    and the most restrictive default wins.

    Parameters
    ----------
    agent : str
        The agent identifier to resolve permissions for.
    permissions : list[PermissionConfig]
        The list of permission rules from the router config.

    Returns
    -------
    ResolvedPermission
        The merged permission state for the agent.
    """
    result = ResolvedPermission(agent=agent)
    matched = False

    for perm in permissions:
        # Check if this rule applies to the agent
        if perm.agent != "*" and perm.agent != agent:
            continue

        matched = True

        # Merge allow/deny lists
        result.allowed_sources.update(perm.allow_sources)
        result.denied_sources.update(perm.deny_sources)
        result.deny_paths.extend(perm.deny_paths)

        # Most restrictive default wins
        if perm.default == "deny":
            result.default = "deny"

    # If no rules matched, use default allow
    if not matched:
        result.default = "allow"

    return result


# ---------------------------------------------------------------------------
# Filtering
# ---------------------------------------------------------------------------


def filter_by_source(
    sources: dict[str, SourceConfig],
    permission: ResolvedPermission,
) -> tuple[list[str], list[str]]:
    """Filter sources by permission, returning (allowed, denied) source names.

    Parameters
    ----------
    sources : dict[str, SourceConfig]
        All available sources keyed by name.
    permission : ResolvedPermission
        The resolved permission for the current agent.

    Returns
    -------
    tuple[list[str], list[str]]
        A tuple of (allowed_source_names, denied_source_names).
    """
    allowed: list[str] = []
    denied: list[str] = []

    for name in sources:
        # Explicit deny takes precedence
        if name in permission.denied_sources:
            denied.append(name)
            continue

        # Explicit allow
        if name in permission.allowed_sources:
            allowed.append(name)
            continue

        # Fall back to default
        if permission.default == "deny":
            denied.append(name)
        else:
            allowed.append(name)

    return allowed, denied


def filter_by_path(
    chunks: list[ContextChunk],
    deny_paths: list[str],
) -> list[ContextChunk]:
    """Filter out chunks whose path matches any deny pattern.

    Parameters
    ----------
    chunks : list[ContextChunk]
        Chunks to filter.
    deny_paths : list[str]
        Glob patterns for paths that should be excluded.

    Returns
    -------
    list[ContextChunk]
        Chunks that do not match any deny path pattern.
    """
    if not deny_paths:
        return chunks

    result: list[ContextChunk] = []
    for chunk in chunks:
        if not chunk.path:
            result.append(chunk)
            continue

        is_denied = False
        for pattern in deny_paths:
            if fnmatch.fnmatch(chunk.path, pattern):
                is_denied = True
                break

        if not is_denied:
            result.append(chunk)

    return result
