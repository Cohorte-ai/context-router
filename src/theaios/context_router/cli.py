"""Click-based CLI: context-router version, validate, inspect, query, cache."""

from __future__ import annotations

import sys

import click

from theaios.context_router import __version__
from theaios.context_router.config import ConfigError, load_config
from theaios.context_router.engine import Router
from theaios.context_router.reporting import (
    export_response_json,
    print_query_result,
    print_router_summary,
)
from theaios.context_router.types import Query


@click.group()
def main() -> None:
    """theaios-context-router — Intelligent context routing for AI agents."""


# ---------------------------------------------------------------------------
# context-router version
# ---------------------------------------------------------------------------


@main.command()
def version() -> None:
    """Show version."""
    click.echo(f"context-router {__version__}")


# ---------------------------------------------------------------------------
# context-router validate
# ---------------------------------------------------------------------------


@main.command()
@click.option(
    "--config", "-c", "config_path", default="context-router.yaml", help="Config file path"
)
def validate(config_path: str) -> None:
    """Validate a configuration file for errors."""
    try:
        config = load_config(config_path)
    except FileNotFoundError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
    except ConfigError as e:
        click.echo("Validation failed:", err=True)
        for error in e.errors:
            click.echo(f"  - {error}", err=True)
        sys.exit(1)

    n_sources = len(config.sources)
    n_routes = len(config.routes)
    n_perms = len(config.permissions)
    click.echo(f"Config is valid: {n_sources} sources, {n_routes} routes, {n_perms} permissions")


# ---------------------------------------------------------------------------
# context-router inspect
# ---------------------------------------------------------------------------


@main.command()
@click.option(
    "--config", "-c", "config_path", default="context-router.yaml", help="Config file path"
)
@click.option("--tag", help="Filter sources by tag")
def inspect(config_path: str, tag: str | None) -> None:
    """Display router configuration: sources, routes, permissions, budget."""
    try:
        config = load_config(config_path)
    except (FileNotFoundError, ConfigError) as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)

    if tag:
        config.sources = {name: s for name, s in config.sources.items() if tag in s.tags}

    print_router_summary(config)


# ---------------------------------------------------------------------------
# context-router query
# ---------------------------------------------------------------------------


@main.command()
@click.option(
    "--config", "-c", "config_path", default="context-router.yaml", help="Config file path"
)
@click.option("--text", "-t", required=True, help="Query text")
@click.option("--agent", "-a", default="default", help="Agent identifier")
@click.option("--output", "-o", type=click.Choice(["console", "json"]), default="console")
@click.option("--output-file", help="Write JSON output to file")
def query(
    config_path: str,
    text: str,
    agent: str,
    output: str,
    output_file: str | None,
) -> None:
    """Execute a context query against the router."""
    try:
        config = load_config(config_path)
    except (FileNotFoundError, ConfigError) as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)

    router = Router(config)
    q = Query(text=text, agent=agent)
    response = router.query(q)

    if output == "json" or output_file:
        json_str = export_response_json(response, output_file)
        if output_file:
            click.echo(f"Exported {len(response.chunks)} chunks to {output_file}")
        else:
            click.echo(json_str)
    else:
        print_query_result(response)


# ---------------------------------------------------------------------------
# context-router cache
# ---------------------------------------------------------------------------


@main.group()
def cache() -> None:
    """Cache management commands."""


@cache.command()
@click.option(
    "--config", "-c", "config_path", default="context-router.yaml", help="Config file path"
)
def stats(config_path: str) -> None:
    """Show cache statistics."""
    try:
        config = load_config(config_path)
    except (FileNotFoundError, ConfigError) as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)

    from theaios.context_router.cache import Cache

    cache_instance = Cache(config.cache)
    cache_stats = cache_instance.stats()

    click.echo(f"Cache: {'enabled' if cache_stats['enabled'] else 'disabled'}")
    click.echo(f"Directory: {cache_stats['directory']}")
    click.echo(f"Entries: {cache_stats['entries']}")
    click.echo(f"Total Size: {cache_stats['total_size_bytes']} bytes")
    click.echo(f"TTL: {cache_stats['ttl']}s")
    click.echo(f"Max Entries: {cache_stats['max_entries']}")


@cache.command()
@click.option(
    "--config", "-c", "config_path", default="context-router.yaml", help="Config file path"
)
@click.option("--source", "-s", help="Only clear entries for this source")
def clear(config_path: str, source: str | None) -> None:
    """Clear cache entries."""
    try:
        config = load_config(config_path)
    except (FileNotFoundError, ConfigError) as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)

    from theaios.context_router.cache import Cache

    cache_instance = Cache(config.cache)
    count = cache_instance.invalidate(source)
    click.echo(f"Cleared {count} cache entries")


main.add_command(cache)
