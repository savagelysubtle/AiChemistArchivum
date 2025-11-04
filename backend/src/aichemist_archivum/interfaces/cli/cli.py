#!/usr/bin/env python
"""
Main CLI application for AIchemist Archivum.

This module provides the main command-line interface for the AIchemist Archivum
file management platform. It includes commands for ingestion, search, tagging,
versioning, analysis, and configuration.
"""

import logging
import sys
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.logging import RichHandler
from rich.panel import Panel
from rich.table import Table

# Configure logging with Rich
console = Console()
logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    handlers=[RichHandler(console=console, rich_tracebacks=True)],
)
logger = logging.getLogger(__name__)

# Main application instance
cli_app = typer.Typer(
    name="archivum",
    help="🧪 AIchemist Archivum - AI-driven file management platform",
    rich_markup_mode="rich",
    no_args_is_help=True,
    add_completion=True,
)

# Command groups
ingest_app = typer.Typer(
    name="ingest",
    help="📥 File ingestion and processing commands",
    rich_markup_mode="rich",
)

search_app = typer.Typer(
    name="search",
    help="🔍 Content search and discovery commands",
    rich_markup_mode="rich",
)

tag_app = typer.Typer(
    name="tag",
    help="🏷️  File tagging and organization commands",
    rich_markup_mode="rich",
)

version_app = typer.Typer(
    name="version",
    help="📋 File versioning and history commands",
    rich_markup_mode="rich",
)

analyze_app = typer.Typer(
    name="analyze",
    help="📊 Content analysis and metrics commands",
    rich_markup_mode="rich",
)

config_app = typer.Typer(
    name="config",
    help="⚙️  Configuration and setup commands",
    rich_markup_mode="rich",
)

# Add sub-applications to main CLI
cli_app.add_typer(ingest_app, name="ingest")
cli_app.add_typer(search_app, name="search")
cli_app.add_typer(tag_app, name="tag")
cli_app.add_typer(version_app, name="version")
cli_app.add_typer(analyze_app, name="analyze")
cli_app.add_typer(config_app, name="config")

# Import command modules to populate the sub-applications
# Note: These imports must come after the sub-apps are created but before they're used
try:
    from .commands import analyze, config, ingest, search, tag, version
except ImportError:
    # Commands will be imported when modules are available
    logger.debug("Command modules not yet available")


# Global options
def version_callback(value: bool) -> None:
    """Show version information."""
    if value:
        console.print("🧪 [bold cyan]AIchemist Archivum[/bold cyan] v0.0.6")
        console.print("AI-driven file management platform")
        raise typer.Exit()


def verbose_callback(value: bool) -> None:
    """Enable verbose output."""
    if value:
        logging.getLogger().setLevel(logging.DEBUG)
        logger.debug("Verbose logging enabled")


@cli_app.callback()
def main(
    version: Annotated[
        bool | None,
        typer.Option(
            "--version", "-v", callback=version_callback, help="Show version and exit"
        ),
    ] = None,
    verbose: Annotated[
        bool,
        typer.Option(
            "--verbose", callback=verbose_callback, help="Enable verbose output"
        ),
    ] = False,
    config_file: Annotated[
        Path | None,
        typer.Option(
            "--config",
            "-c",
            help="Path to configuration file",
            exists=False,
            file_okay=True,
            dir_okay=False,
            readable=True,
        ),
    ] = None,
) -> None:
    """
    🧪 AIchemist Archivum - AI-driven file management platform

    A comprehensive tool for intelligent file ingestion, tagging, versioning,
    and analysis. Uses AI to extract metadata, build relationships, and provide
    semantic search capabilities.

    [bold]Common workflows:[/bold]

    • [cyan]archivum ingest path/to/folder[/cyan] - Ingest files from a directory
    • [cyan]archivum search "query text"[/cyan] - Search content semantically
    • [cyan]archivum tag add file.txt important[/cyan] - Add tags to files
    • [cyan]archivum analyze relationships[/cyan] - Analyze file relationships
    • [cyan]archivum config init[/cyan] - Initialize configuration
    """
    if config_file:
        logger.debug(f"Using config file: {config_file}")


# Utility functions for CLI commands
async def run_async_command(coro):
    """Helper to run async commands in CLI context."""
    try:
        return await coro
    except Exception as e:
        logger.error(f"Command failed: {e}")
        console.print(f"❌ [red]Error:[/red] {e}")
        raise typer.Exit(1)


def validate_path_exists(path: Path) -> Path:
    """Validate that a path exists."""
    if not path.exists():
        console.print(f"❌ [red]Error:[/red] Path does not exist: {path}")
        raise typer.Exit(1)
    return path


def format_file_size(size_bytes: int) -> str:
    """Format file size in human readable format."""
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} PB"


def display_results_table(results: list, title: str = "Results") -> None:
    """Display results in a formatted table."""
    if not results:
        console.print(f"ℹ️ No {title.lower()} found.")
        return

    table = Table(title=title, show_header=True, header_style="bold cyan")

    # Dynamically add columns based on first result
    if results and isinstance(results[0], dict):
        for key in results[0].keys():
            table.add_column(str(key).title())

        for result in results:
            table.add_row(*[str(value) for value in result.values()])
    else:
        table.add_column("Item")
        for result in results:
            table.add_row(str(result))

    console.print(table)


# Status and info commands for main app
@cli_app.command()
def status() -> None:
    """
    📊 Show system status and statistics

    Displays current system status, database information,
    and basic statistics about ingested files.
    """
    console.print(Panel.fit("🧪 [bold cyan]AIchemist Archivum Status[/bold cyan]"))

    # This would be implemented with actual service calls
    status_info = {
        "Status": "✅ Running",
        "Database": "📁 SQLite (Connected)",
        "Files Indexed": "1,234",
        "Tags Created": "56",
        "Version Count": "789",
        "Last Ingestion": "2 hours ago",
    }

    table = Table(show_header=False, box=None)
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")

    for metric, value in status_info.items():
        table.add_row(metric, value)

    console.print(table)


@cli_app.command()
def info() -> None:
    """
    ℹ️  Show detailed system information

    Displays comprehensive information about the system configuration,
    capabilities, and current state.
    """
    console.print(Panel.fit("🧪 [bold cyan]System Information[/bold cyan]"))

    info_data = {
        "Version": "0.0.6",
        "Python": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        "Platform": sys.platform,
        "Config Location": "~/.config/aichemist-archivum/",
        "Data Directory": "./data/",
        "Supported Formats": "Text, PDF, DOCX, Images, Code files",
        "Search Providers": "Regex, Similarity, Semantic",
        "Analysis Features": "Code metrics, Relationships, Tech stack",
    }

    table = Table(show_header=False, box=None)
    table.add_column("Property", style="cyan", width=20)
    table.add_column("Value", style="white")

    for prop, value in info_data.items():
        table.add_row(prop, value)

    console.print(table)


if __name__ == "__main__":
    cli_app()
