"""Rich terminal output for router inspection and query results."""

from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from theaios.context_router.types import ContextResponse, RouterConfig

console = Console()


def print_router_summary(config: RouterConfig) -> None:
    """Print a formatted summary of a router configuration."""
    if config.metadata.name:
        console.print(f"\n[bold]{config.metadata.name}[/bold]")
    if config.metadata.description:
        console.print(f"  {config.metadata.description}")
    console.print(f"  Version: {config.version}")
    if config.metadata.author:
        console.print(f"  Author: {config.metadata.author}")

    # Sources
    if config.sources:
        console.print(f"\n[bold]Sources[/bold] ({len(config.sources)})")
        table = Table(show_header=True, header_style="bold")
        table.add_column("Name")
        table.add_column("Type")
        table.add_column("Enabled")
        table.add_column("Priority")
        table.add_column("Tags")
        for name, source in config.sources.items():
            type_color = {
                "inline": "cyan",
                "directory": "green",
                "git_repo": "yellow",
                "http_api": "magenta",
            }.get(source.type, "white")
            table.add_row(
                name,
                f"[{type_color}]{source.type}[/{type_color}]",
                "[green]yes[/green]" if source.enabled else "[red]no[/red]",
                str(source.priority),
                ", ".join(source.tags) or "-",
            )
        console.print(table)

    # Routes
    if config.routes:
        console.print(f"\n[bold]Routes[/bold] ({len(config.routes)})")
        table = Table(show_header=True, header_style="bold")
        table.add_column("Name")
        table.add_column("When")
        table.add_column("Sources")
        table.add_column("Enabled")
        for route in config.routes:
            table.add_row(
                route.name,
                route.when or "[dim]always[/dim]",
                ", ".join(route.sources),
                "[green]yes[/green]" if route.enabled else "[red]no[/red]",
            )
        console.print(table)

    # Permissions
    if config.permissions:
        console.print(f"\n[bold]Permissions[/bold] ({len(config.permissions)})")
        table = Table(show_header=True, header_style="bold")
        table.add_column("Agent")
        table.add_column("Allow")
        table.add_column("Deny")
        table.add_column("Deny Paths")
        table.add_column("Default")
        for perm in config.permissions:
            default_color = "green" if perm.default == "allow" else "red"
            table.add_row(
                perm.agent,
                ", ".join(perm.allow_sources) or "-",
                ", ".join(perm.deny_sources) or "-",
                ", ".join(perm.deny_paths) or "-",
                f"[{default_color}]{perm.default}[/{default_color}]",
            )
        console.print(table)

    # Budget
    console.print("\n[bold]Budget[/bold]")
    budget_table = Table(show_header=False)
    budget_table.add_column("Setting", style="dim")
    budget_table.add_column("Value")
    budget_table.add_row("Max Tokens", str(config.budget.max_tokens))
    budget_table.add_row("Ranking", config.budget.ranking)
    budget_table.add_row("Truncation", config.budget.truncation)
    budget_table.add_row("Estimator", config.budget.estimator)
    budget_table.add_row("Reserve Tokens", str(config.budget.reserve_tokens))
    console.print(budget_table)

    # Cache
    console.print("\n[bold]Cache[/bold]")
    cache_status = "[green]enabled[/green]" if config.cache.enabled else "[dim]disabled[/dim]"
    console.print(f"  Status: {cache_status}")
    if config.cache.enabled:
        console.print(f"  Directory: {config.cache.directory}")
        console.print(f"  TTL: {config.cache.ttl}s")
        console.print(f"  Max Entries: {config.cache.max_entries}")

    console.print()


def print_query_result(response: ContextResponse) -> None:
    """Print a formatted query result."""
    # Summary header
    n_chunks = len(response.chunks)
    status_color = "green" if n_chunks > 0 else "yellow"
    console.print(
        f"\n[bold {status_color}]{n_chunks} chunk(s)[/bold {status_color}] "
        f"| {response.total_tokens} tokens"
        f"{'  [dim][truncated][/dim]' if response.was_truncated else ''}"
    )

    if response.matched_routes:
        console.print(f"  Routes: {', '.join(response.matched_routes)}")
    if response.denied_sources:
        console.print(f"  [red]Denied sources: {', '.join(response.denied_sources)}[/red]")

    console.print(f"  Evaluated in: {response.evaluation_time_ms:.2f}ms")

    # Chunks table
    if response.chunks:
        console.print()
        table = Table(show_header=True, header_style="bold")
        table.add_column("#", style="dim")
        table.add_column("Source")
        table.add_column("Title")
        table.add_column("Path")
        table.add_column("Tokens", justify="right")
        table.add_column("Score", justify="right")

        for i, chunk in enumerate(response.chunks, 1):
            table.add_row(
                str(i),
                chunk.source,
                chunk.title or "-",
                chunk.path or "-",
                str(chunk.token_count),
                f"{chunk.relevance_score:.2f}",
            )
        console.print(table)

        # Show content preview for each chunk
        for i, chunk in enumerate(response.chunks, 1):
            preview = chunk.content[:200]
            if len(chunk.content) > 200:
                preview += "..."
            console.print(
                Panel(
                    preview,
                    title=f"[bold]Chunk {i}[/bold] — {chunk.title or chunk.source}",
                    border_style="dim",
                )
            )

    console.print()
