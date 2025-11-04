"""
Tag Management Commands for AIchemist Archivum CLI.

This module provides commands for adding, removing, listing, and managing tags
on files and content. Tags enable organization, search, and categorization.
"""

import asyncio
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from aichemist_archivum.services.database_service import DatabaseService

from ..cli import tag_app

console = Console()


@tag_app.command("add")
def add_tags(
    file_path: Annotated[
        Path,
        typer.Argument(
            help="Path to the file to tag",
            exists=True,
            file_okay=True,
            dir_okay=False,
            readable=True,
        ),
    ],
    tags: Annotated[list[str], typer.Argument(help="Tags to add to the file")],
) -> None:
    """
    🏷️  Add tags to a file

    Examples:
    • [cyan]python start.py tag add document.pdf important urgent[/cyan]
    • [cyan]python start.py tag add code/script.py python automation[/cyan]
    """
    asyncio.run(_add_tags_async(file_path, tags))


async def _add_tags_async(file_path: Path, tags: list[str]) -> None:
    """Async implementation of tag addition."""
    console.print(f"🏷️  [bold cyan]Adding tags to:[/bold cyan] {file_path}")
    console.print(f"Tags: {', '.join(tags)}")

    try:
        database_service = DatabaseService()

        # Check if file exists in database
        file_info = await database_service.get_file_by_path(file_path)

        if not file_info:
            console.print(f"❌ [red]File not found in database:[/red] {file_path}")
            console.print(
                "💡 Ingest the file first: [cyan]python start.py ingest file {file_path}[/cyan]"
            )
            return

        # Add tags to file
        await database_service.add_tags_to_file(file_path, tags)

        console.print("✅ [green]Tags added successfully![/green]")

        # Show current tags
        current_tags = await database_service.get_file_tags(file_path)
        if current_tags:
            console.print(
                f"\n📋 Current tags: {', '.join([t['name'] for t in current_tags])}"
            )

    except Exception as e:
        console.print(f"❌ [red]Error adding tags:[/red] {e}")


@tag_app.command("remove")
def remove_tags(
    file_path: Annotated[
        Path,
        typer.Argument(
            help="Path to the file",
            exists=True,
            file_okay=True,
            dir_okay=False,
            readable=True,
        ),
    ],
    tags: Annotated[list[str], typer.Argument(help="Tags to remove from the file")],
) -> None:
    """
    🗑️  Remove tags from a file

    Examples:
    • [cyan]python start.py tag remove document.pdf urgent[/cyan]
    • [cyan]python start.py tag remove script.py old deprecated[/cyan]
    """
    asyncio.run(_remove_tags_async(file_path, tags))


async def _remove_tags_async(file_path: Path, tags: list[str]) -> None:
    """Async implementation of tag removal."""
    console.print(f"🗑️  [bold cyan]Removing tags from:[/bold cyan] {file_path}")
    console.print(f"Tags to remove: {', '.join(tags)}")

    try:
        database_service = DatabaseService()

        # Check if file exists in database
        file_info = await database_service.get_file_by_path(file_path)

        if not file_info:
            console.print(f"❌ [red]File not found in database:[/red] {file_path}")
            return

        # Remove tags from file
        await database_service.remove_tags_from_file(file_path, tags)

        console.print("✅ [green]Tags removed successfully![/green]")

        # Show remaining tags
        remaining_tags = await database_service.get_file_tags(file_path)
        if remaining_tags:
            console.print(
                f"📋 Remaining tags: {', '.join([t['name'] for t in remaining_tags])}"
            )
        else:
            console.print("📋 No tags remaining on this file")

    except Exception as e:
        console.print(f"❌ [red]Error removing tags:[/red] {e}")


@tag_app.command("list")
def list_tags(
    file_path: Annotated[
        Path | None,
        typer.Argument(help="Path to file (optional - omit to list all tags)"),
    ] = None,
    show_counts: Annotated[
        bool, typer.Option("--counts", "-c", help="Show usage counts")
    ] = False,
    sort_by: Annotated[
        str, typer.Option("--sort", "-s", help="Sort by (name, count, date)")
    ] = "name",
) -> None:
    """
    📋 List tags

    Examples:
    • [cyan]python start.py tag list[/cyan]
    • [cyan]python start.py tag list --counts[/cyan]
    • [cyan]python start.py tag list document.pdf[/cyan]
    """
    asyncio.run(_list_tags_async(file_path, show_counts, sort_by))


async def _list_tags_async(
    file_path: Path | None, show_counts: bool, sort_by: str
) -> None:
    """Async implementation of tag listing."""
    if file_path:
        console.print(f"🏷️  [bold cyan]Tags for:[/bold cyan] {file_path}")

        try:
            database_service = DatabaseService()

            # Get tags for specific file
            tags = await database_service.get_file_tags(file_path)

            if not tags:
                console.print("📋 No tags found for this file")
                return

            table = Table(
                title=f"Tags for {file_path.name}",
                show_header=True,
                header_style="bold cyan",
            )
            table.add_column("Tag", style="white")
            table.add_column("Added", style="blue")

            for tag in tags:
                table.add_row(
                    tag["name"],
                    str(tag.get("added_at", ""))[:19] if tag.get("added_at") else "-",
                )

            console.print(table)

        except Exception as e:
            console.print(f"❌ [red]Error listing tags:[/red] {e}")
    else:
        console.print("🏷️  [bold cyan]All tags in system[/bold cyan]")

        try:
            database_service = DatabaseService()

            # Get all tags
            all_tags = await database_service.get_all_tags()

            if not all_tags:
                console.print("📋 No tags found in system")
                return

            # Sort tags
            if sort_by == "name":
                all_tags.sort(key=lambda x: x["name"])
            elif sort_by == "count" and show_counts:
                all_tags.sort(key=lambda x: x.get("usage_count", 0), reverse=True)
            elif sort_by == "date":
                all_tags.sort(key=lambda x: x.get("created_at", ""), reverse=True)

            table = Table(
                title="All Tags",
                show_header=True,
                header_style="bold cyan",
            )
            table.add_column("Tag", style="white")

            if show_counts:
                table.add_column("Files", style="yellow", justify="right")

            table.add_column("Category", style="blue")

            for tag in all_tags:
                if show_counts:
                    table.add_row(
                        tag["name"],
                        str(tag.get("usage_count", 0)),
                        tag.get("category", "-") or "-",
                    )
                else:
                    table.add_row(tag["name"], tag.get("category", "-") or "-")

            console.print(table)
            console.print(f"\n📊 Total tags: {len(all_tags)}")

        except Exception as e:
            console.print(f"❌ [red]Error listing tags:[/red] {e}")


@tag_app.command("create")
def create_tag(
    name: Annotated[str, typer.Argument(help="Tag name")],
    description: Annotated[
        str | None, typer.Option("--description", "-d", help="Tag description")
    ] = None,
    category: Annotated[
        str | None, typer.Option("--category", "-c", help="Tag category")
    ] = None,
) -> None:
    """
    ➕ Create a new tag

    Examples:
    • [cyan]python start.py tag create urgent --description "Urgent items" --category priority[/cyan]
    • [cyan]python start.py tag create python-code --category language[/cyan]
    """
    asyncio.run(_create_tag_async(name, description, category))


async def _create_tag_async(
    name: str, description: str | None, category: str | None
) -> None:
    """Async implementation of tag creation."""
    console.print(f"➕ [bold cyan]Creating tag:[/bold cyan] {name}")

    try:
        database_service = DatabaseService()

        # Create the tag
        tag_id = await database_service.create_tag(name, description, category)

        console.print("✅ [green]Tag created successfully![/green]")

        # Display tag info
        table = Table(show_header=False, box=None)
        table.add_column("Property", style="cyan", width=15)
        table.add_column("Value", style="white")

        table.add_row("ID", str(tag_id))
        table.add_row("Name", name)
        if description:
            table.add_row("Description", description)
        if category:
            table.add_row("Category", category)

        console.print(table)

    except Exception as e:
        console.print(f"❌ [red]Error creating tag:[/red] {e}")


@tag_app.command("stats")
def tag_stats() -> None:
    """
    📊 Show tag usage statistics

    Displays statistics about tag usage in the system.

    Examples:
    • [cyan]python start.py tag stats[/cyan]
    """
    asyncio.run(_tag_stats_async())


async def _tag_stats_async() -> None:
    """Async implementation of tag statistics."""
    console.print("📊 [bold cyan]Tag Usage Statistics[/bold cyan]")

    try:
        database_service = DatabaseService()
        stats = await database_service.get_statistics()

        table = Table(show_header=False, box=None)
        table.add_column("Metric", style="cyan", width=25)
        table.add_column("Value", style="white", justify="right")

        table.add_row("Total tags", str(stats.get("total_tags", 0)))
        table.add_row("Tagged files", str(stats.get("total_file_tags", 0)))
        table.add_row("Avg tags per file", str(stats.get("avg_tags_per_file", 0)))

        console.print(table)

    except Exception as e:
        console.print(f"❌ [red]Error getting stats:[/red] {e}")
