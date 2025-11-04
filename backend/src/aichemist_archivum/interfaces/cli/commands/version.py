"""
Versioning commands for AIchemist Archivum CLI.

This module provides commands for managing file versions, viewing history,
creating diffs, and restoring previous versions.
"""

import asyncio
import logging
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress
from rich.syntax import Syntax
from rich.table import Table

from aichemist_archivum.services.versioning_service import VersionManager

from ..cli import version_app

console = Console()
logger = logging.getLogger(__name__)


@version_app.command("create")
def create_version(
    file_path: Annotated[
        Path,
        typer.Argument(
            help="Path to the file to version",
            exists=True,
            file_okay=True,
            dir_okay=False,
            readable=True,
        ),
    ],
    message: Annotated[
        str | None, typer.Option("--message", "-m", help="Version message/annotation")
    ] = None,
    author: Annotated[
        str | None, typer.Option("--author", "-a", help="Author of this version")
    ] = None,
    tags: Annotated[
        list[str] | None, typer.Option("--tag", "-t", help="Tags for this version")
    ] = None,
    force: Annotated[
        bool,
        typer.Option(
            "--force", "-f", help="Force version creation even if no changes detected"
        ),
    ] = False,
) -> None:
    """
    📋 Create a new version of a file

    Creates a new version snapshot of the specified file.
    Versions can include messages, author information, and tags.

    [bold]Examples:[/bold]

    • [cyan]archivum version create script.py --message "Fixed bug in parser"[/cyan]
    • [cyan]archivum version create document.md --author "John Doe" --tag release[/cyan]
    • [cyan]archivum version create config.json --force[/cyan]
    """
    asyncio.run(_create_version_async(file_path, message, author, tags or [], force))


async def _create_version_async(
    file_path: Path,
    message: str | None,
    author: str | None,
    tags: list[str],
    force: bool,
) -> None:
    """Async implementation of version creation."""
    console.print(f"📋 [bold cyan]Creating version for:[/bold cyan] {file_path.name}")

    if message:
        console.print(f"💬 Message: {message}")
    if author:
        console.print(f"👤 Author: {author}")
    if tags:
        console.print(f"🏷️  Tags: {', '.join(tags)}")

    try:
        # Initialize version manager
        version_manager = VersionManager()

        # Create version
        metadata = await version_manager.create_version(
            file_path,
            manual=True,
            annotation=message or "",
            author=author or "",
            tags=tags,
        )

        console.print("✅ [green]Version created successfully[/green]")

        # Display version info
        info_table = Table(show_header=False, box=None)
        info_table.add_column("Property", style="cyan", width=15)
        info_table.add_column("Value", style="white")

        info_table.add_row("Version ID", metadata.version_id)
        info_table.add_row("File", str(file_path))
        info_table.add_row("Type", metadata.version_type.value.title())
        info_table.add_row("Created", str(metadata.timestamp))
        if metadata.author:
            info_table.add_row("Author", metadata.author)
        if metadata.annotation:
            info_table.add_row("Message", metadata.annotation)
        if metadata.tags:
            info_table.add_row("Tags", ", ".join(metadata.tags))

        console.print(info_table)

    except Exception as e:
        console.print(f"❌ [red]Error creating version:[/red] {e}")
        raise typer.Exit(1) from e


@version_app.command("history")
def show_history(
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
    limit: Annotated[
        int, typer.Option("--limit", "-n", help="Maximum number of versions to show")
    ] = 10,
    show_details: Annotated[
        bool, typer.Option("--details", "-d", help="Show detailed version information")
    ] = False,
    show_diff: Annotated[
        bool, typer.Option("--diff", help="Show diff for each version")
    ] = False,
) -> None:
    """
    📜 Show version history for a file

    Displays the version history for a file, including version IDs,
    creation dates, authors, and messages.

    [bold]Examples:[/bold]

    • [cyan]archivum version history script.py[/cyan]
    • [cyan]archivum version history document.md --limit 5 --details[/cyan]
    • [cyan]archivum version history config.json --diff[/cyan]
    """
    asyncio.run(_show_history_async(file_path, limit, show_details, show_diff))


async def _show_history_async(
    file_path: Path, limit: int, show_details: bool, show_diff: bool
) -> None:
    """Async implementation of showing version history."""
    console.print(f"📜 [bold cyan]Version history for:[/bold cyan] {file_path.name}")

    try:
        version_manager = VersionManager()
        versions = await version_manager.list_versions(file_path)

        if not versions:
            console.print("📭 [dim]No version history found[/dim]")
            return

        # Limit results
        versions = versions[:limit]

        console.print(f"📊 Showing {len(versions)} version(s)")

        if show_details:
            for i, version in enumerate(versions):
                # Create a panel for each version
                version_info = []
                version_info.append(f"[bold]Version:[/bold] {version.version_id}")
                version_info.append(
                    f"[bold]Type:[/bold] {version.version_type.value.title()}"
                )
                if version.author:
                    version_info.append(f"[bold]Author:[/bold] {version.author}")
                version_info.append(f"[bold]Created:[/bold] {version.timestamp}")

                if version.annotation:
                    version_info.append(f"[bold]Message:[/bold] {version.annotation}")

                if version.tags:
                    version_info.append(f"[bold]Tags:[/bold] {', '.join(version.tags)}")

                panel = Panel(
                    "\n".join(version_info),
                    title=f"Version {i + 1}",
                    border_style="cyan" if i == 0 else "dim",
                )
                console.print(panel)

                if show_diff and i < len(versions) - 1:
                    console.print("[dim]Diff not yet implemented[/dim]")

        else:
            # Create a table for compact view
            table = Table(title="Version History")
            table.add_column("Version ID", style="cyan")
            table.add_column("Type", style="yellow")
            table.add_column("Created", style="green")
            table.add_column("Author", style="magenta")
            table.add_column("Message", style="white")

            for version in versions:
                table.add_row(
                    version.version_id[:12] + "...",  # Shortened ID
                    version.version_type.value.title(),
                    str(version.timestamp)[:19],  # Just datetime
                    version.author or "-",
                    (version.annotation[:50] + "...")
                    if len(version.annotation or "") > 50
                    else (version.annotation or "-"),
                )

            console.print(table)

    except Exception as e:
        console.print(f"❌ [red]Error retrieving version history:[/red] {e}")
        raise typer.Exit(1) from e


@version_app.command("diff")
def show_diff(
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
    version1: Annotated[
        str | None,
        typer.Option("--from", help="First version ID (defaults to previous version)"),
    ] = None,
    version2: Annotated[
        str | None,
        typer.Option("--to", help="Second version ID (defaults to current version)"),
    ] = None,
    unified: Annotated[
        int, typer.Option("--unified", "-u", help="Number of context lines")
    ] = 3,
    word_diff: Annotated[
        bool, typer.Option("--word-diff", help="Show word-level differences")
    ] = False,
) -> None:
    """
    🔄 Show differences between file versions

    Displays the differences between two versions of a file.
    If no versions are specified, shows diff between latest and previous.

    [bold]Examples:[/bold]

    • [cyan]archivum version diff script.py[/cyan]
    • [cyan]archivum version diff document.md --from v1.2.0 --to v1.3.0[/cyan]
    • [cyan]archivum version diff config.json --word-diff[/cyan]
    """
    asyncio.run(_show_diff_async(file_path, version1, version2, unified, word_diff))


async def _show_diff_async(
    file_path: Path,
    version1: str | None,
    version2: str | None,
    unified: int,
    word_diff: bool,
) -> None:
    """Async implementation of showing diff."""
    console.print(f"🔄 [bold cyan]Showing diff for:[/bold cyan] {file_path.name}")

    try:
        import difflib

        from aichemist_archivum.services.versioning_service import VersionManager

        version_manager = VersionManager()

        # Get versions list to determine which versions to compare
        versions = await version_manager.list_versions(file_path)

        if not versions:
            console.print("❌ [red]No versions found for this file[/red]")
            raise typer.Exit(1)

        # Determine versions to compare
        if not version1:
            # Compare latest two versions
            if len(versions) < 2:
                console.print("❌ [red]Need at least 2 versions to compare[/red]")
                raise typer.Exit(1)
            version1 = versions[1].version_id  # Second latest
            version2 = versions[0].version_id if not version2 else version2  # Latest
        elif not version2:
            version2 = versions[0].version_id  # Latest

        console.print(
            f"📋 Comparing: [blue]{version1}[/blue] → [green]{version2}[/green]"
        )

        # Get version content
        with Progress() as progress:
            task = progress.add_task("Loading versions...", total=100)

            # Get both versions
            progress.update(task, advance=50)
            version1_path, _version1_meta = await version_manager.get_version(
                file_path, version1
            )
            version2_path, _version2_meta = await version_manager.get_version(
                file_path, version2
            )

            progress.update(task, advance=50)

        if not version1_path or not version2_path:
            console.print("❌ [red]Could not load version content[/red]")
            raise typer.Exit(1)

        # Read the files
        with open(version1_path, encoding="utf-8", errors="ignore") as f:
            content1 = f.readlines()
        with open(version2_path, encoding="utf-8", errors="ignore") as f:
            content2 = f.readlines()

        # Generate diff
        if word_diff:
            # Word-level diff (simplified)
            diff_lines = []
            for line1, line2 in zip(content1, content2, strict=False):
                if line1 != line2:
                    diff_lines.append(f"[-{line1.rstrip()}-] {{+{line2.rstrip()}+}}")
                else:
                    diff_lines.append(line1.rstrip())
            diff_content = "\n".join(diff_lines[:50])  # Limit to 50 lines
            console.print(Panel(diff_content, title="Word Diff", border_style="yellow"))
        else:
            # Unified diff
            diff = difflib.unified_diff(
                content1,
                content2,
                fromfile=f"Version {version1}",
                tofile=f"Version {version2}",
                lineterm="",
                n=unified,
            )
            diff_content = "\n".join(list(diff)[:100])  # Limit to 100 lines

            if diff_content:
                syntax = Syntax(
                    diff_content, "diff", theme="monokai", line_numbers=False
                )
                console.print(Panel(syntax, title="Unified Diff", border_style="green"))
            else:
                console.print("✨ [green]No differences found[/green]")
                return

        # Calculate statistics
        additions = sum(1 for line in content2 if line not in content1)
        deletions = sum(1 for line in content1 if line not in content2)

        # Show diff statistics
        stats_table = Table(show_header=False, box=None)
        stats_table.add_column("Metric", style="cyan", width=15)
        stats_table.add_column("Value", style="white")

        stats_table.add_row("Lines added", f"[green]+{additions}[/green]")
        stats_table.add_row("Lines removed", f"[red]-{deletions}[/red]")
        stats_table.add_row("Total changes", str(additions + deletions))

        console.print("\n📊 [bold]Diff Statistics:[/bold]")
        console.print(stats_table)

    except Exception as e:
        console.print(f"❌ [red]Error generating diff:[/red] {e}")
        import traceback

        console.print(f"[dim]{traceback.format_exc()}[/dim]")
        raise typer.Exit(1) from None


@version_app.command("restore")
def restore_version(
    file_path: Annotated[
        Path,
        typer.Argument(
            help="Path to the file to restore",
            exists=True,
            file_okay=True,
            dir_okay=False,
            readable=True,
        ),
    ],
    version_id: Annotated[str, typer.Argument(help="Version ID to restore")],
    backup: Annotated[
        bool,
        typer.Option(
            "--backup", "-b", help="Create backup of current version before restoring"
        ),
    ] = True,
    force: Annotated[
        bool, typer.Option("--force", "-f", help="Force restore without confirmation")
    ] = False,
) -> None:
    """
    ⏪ Restore a file to a previous version

    Restores the file to the specified version. By default, creates
    a backup of the current version before restoring.

    [bold]Examples:[/bold]

    • [cyan]archivum version restore script.py v1.2.0-abc123[/cyan]
    • [cyan]archivum version restore document.md v1.0.0-xyz789 --no-backup[/cyan]
    • [cyan]archivum version restore config.json v2.1.0-def456 --force[/cyan]
    """
    asyncio.run(_restore_version_async(file_path, version_id, backup, force))


async def _restore_version_async(
    file_path: Path, version_id: str, backup: bool, force: bool
) -> None:
    """Async implementation of version restoration."""
    console.print(f"⏪ [bold yellow]Restoring file:[/bold yellow] {file_path.name}")
    console.print(f"📋 Target version: [blue]{version_id}[/blue]")

    try:
        import shutil
        from datetime import datetime

        from aichemist_archivum.services.versioning_service import VersionManager

        version_manager = VersionManager()

        # Get the specified version
        version_path, version_meta = await version_manager.get_version(
            file_path, version_id
        )

        if not version_path or not version_meta:
            console.print(f"❌ [red]Error:[/red] Version '{version_id}' not found")

            # Show available versions
            versions = await version_manager.list_versions(file_path)
            if versions:
                console.print("\n📋 [bold]Available versions:[/bold]")
                for v in versions[:5]:
                    console.print(f"  • {v.version_id} - {v.timestamp}")
            raise typer.Exit(1)

        # Confirm if not forced
        if not force:
            confirm = typer.confirm(
                f"\nRestore {file_path.name} to version {version_id}?", default=False
            )
            if not confirm:
                console.print("❌ [yellow]Restore cancelled[/yellow]")
                raise typer.Exit(0)

        # Create backup if requested
        if backup and file_path.exists():
            backup_path = file_path.with_suffix(
                f".backup-{datetime.now().strftime('%Y%m%d_%H%M%S')}{file_path.suffix}"
            )
            console.print(f"💾 Creating backup: {backup_path.name}")
            shutil.copy2(file_path, backup_path)

        # Restore the version
        with Progress() as progress:
            task = progress.add_task("Restoring version...", total=100)
            progress.update(task, advance=50)

            # Copy the version file to the original location
            shutil.copy2(version_path, file_path)

            progress.update(task, advance=50)

        console.print("✅ [green]Version restored successfully![/green]")

        # Show summary
        summary_table = Table(show_header=False, box=None)
        summary_table.add_column("Info", style="cyan", width=20)
        summary_table.add_column("Value", style="white")

        summary_table.add_row("File", str(file_path.name))
        summary_table.add_row("Restored version", version_id)
        summary_table.add_row("Version created", str(version_meta.timestamp))
        if backup:
            summary_table.add_row("Backup created", "✓")

        console.print("\n📊 [bold]Restore Summary:[/bold]")
        console.print(summary_table)

    except typer.Exit:
        raise
    except Exception as e:
        console.print(f"❌ [red]Error during restore:[/red] {e}")
        import traceback

        console.print(f"[dim]{traceback.format_exc()}[/dim]")
        raise typer.Exit(1) from None


@version_app.command("list")
def list_versions() -> None:
    """
    📋 List all files with versions

    Shows all files in the system that have version history,
    along with their version counts and latest version info.
    """
    asyncio.run(_list_versions_async())


async def _list_versions_async() -> None:
    """Async implementation of version list."""
    console.print("📋 [bold cyan]Files with Version History[/bold cyan]")

    try:
        from aichemist_archivum.config.settings import determine_project_root
        from aichemist_archivum.services.versioning_service import VersionManager

        VersionManager()
        project_root = determine_project_root()
        metadata_dir = project_root / "data" / "versions" / "metadata"

        if not metadata_dir.exists():
            console.print("📭 [dim]No version metadata directory found[/dim]")
            console.print(
                "💡 Tip: Create versions with "
                "[cyan]archivum version create <file>[/cyan]"
            )
            return

        # Scan for version graph files
        version_files = {}
        for meta_file in metadata_dir.glob("*.json"):
            try:
                # Extract file path from metadata filename
                # Format: <hash>_versions.json
                import json

                with open(meta_file) as f:
                    data = json.load(f)
                    if data.get("versions"):
                        file_path = data["versions"][0].get("file_path", "unknown")
                        version_count = len(data["versions"])
                        latest = data["versions"][0]

                        version_files[file_path] = {
                            "versions": version_count,
                            "latest": latest.get("version_id", "unknown"),
                            "last_modified": latest.get("created_at", "unknown"),
                        }
            except Exception as e:
                logger.debug(f"Error reading metadata file {meta_file}: {e}")
                continue

        if not version_files:
            console.print("📭 [dim]No versioned files found[/dim]")
            console.print(
                "💡 Tip: Create versions with "
                "[cyan]archivum version create <file>[/cyan]"
            )
            return

        console.print(f"📊 Found {len(version_files)} versioned files")

        table = Table(
            title="Versioned Files", show_header=True, header_style="bold cyan"
        )
        table.add_column("File", style="white", width=40)
        table.add_column("Versions", style="green", width=10, justify="right")
        table.add_column("Latest Version", style="blue", width=25)
        table.add_column("Last Modified", style="magenta", width=25)

        for file_path, file_info in sorted(version_files.items()):
            # Truncate long paths
            display_path = file_path if len(file_path) < 40 else "..." + file_path[-37:]

            table.add_row(
                display_path,
                str(file_info["versions"]),
                file_info["latest"],
                str(file_info["last_modified"]),
            )

        console.print(table)

    except Exception as e:
        console.print(f"❌ [red]Error listing versions:[/red] {e}")
        import traceback

        console.print(f"[dim]{traceback.format_exc()}[/dim]")


@version_app.command("info")
def version_info(
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
    version_id: Annotated[
        str | None, typer.Option("--version", "-v", help="Specific version ID")
    ] = None,
) -> None:
    """Show detailed information about a specific version.

    Displays comprehensive information about a version including
    metadata, changes, and related versions.

    [bold]Examples:[/bold]

    • [cyan]archivum version info script.py --version v1.2.3-abc123def[/cyan]
    • [cyan]archivum version info document.md[/cyan] (shows latest version info)
    """
    asyncio.run(_version_info_async(file_path, version_id))


async def _version_info_async(file_path: Path, version_id: str | None) -> None:
    """Async implementation of version info."""
    try:
        from aichemist_archivum.services.versioning_service import VersionManager

        version_manager = VersionManager()

        # Get versions list
        versions = await version_manager.list_versions(file_path)

        if not versions:
            console.print(f"❌ [red]No versions found for:[/red] {file_path.name}")
            raise typer.Exit(1)

        # Get specific version or latest
        if version_id:
            target_version = next(
                (v for v in versions if v.version_id == version_id), None
            )
            if not target_version:
                console.print(f"❌ [red]Version not found:[/red] {version_id}")
                console.print("\n💡 Available versions:")
                for v in versions[:5]:
                    console.print(f"  • {v.version_id}")
                raise typer.Exit(1)
        else:
            target_version = versions[0]  # Latest

        console.print("[bold cyan]ℹ Version Information[/bold cyan]")
        console.print()

        # Main info panel
        info_lines = [
            f"[bold]Version ID:[/bold] {target_version.version_id}",
            f"[bold]File:[/bold] {target_version.file_path}",
            f"[bold]Type:[/bold] {target_version.version_type.value}",
            f"[bold]Created:[/bold] {target_version.timestamp}",
            f"[bold]Size:[/bold] {target_version.size_bytes:,} bytes",
        ]

        if target_version.author:
            info_lines.append(f"[bold]Author:[/bold] {target_version.author}")

        if target_version.change_description:
            info_lines.append(
                f"[bold]Description:[/bold] {target_version.change_description}"
            )

        if target_version.parent_version_id:
            info_lines.append(
                f"[bold]Parent Version:[/bold] {target_version.parent_version_id}"
            )

        panel_content = "\n".join(info_lines)
        console.print(
            Panel(panel_content, title="📋 Version Details", border_style="cyan")
        )

        # Tags
        if target_version.tags:
            console.print(f"\n🏷️  [bold]Tags:[/bold] {', '.join(target_version.tags)}")

        # Change metrics
        if target_version.change_percentage > 0:
            console.print("\n📊 [bold]Changes:[/bold]")
            metrics_table = Table(show_header=False, box=None)
            metrics_table.add_column("Metric", style="cyan", width=20)
            metrics_table.add_column("Value", style="white")

            metrics_table.add_row(
                "Change Percentage", f"{target_version.change_percentage:.1f}%"
            )

            if target_version.lines_added > 0 or target_version.lines_removed > 0:
                metrics_table.add_row(
                    "Lines Added", f"[green]+{target_version.lines_added}[/green]"
                )
                metrics_table.add_row(
                    "Lines Removed", f"[red]-{target_version.lines_removed}[/red]"
                )

            console.print(metrics_table)

        # Version history position
        version_index = next(
            (
                i
                for i, v in enumerate(versions)
                if v.version_id == target_version.version_id
            ),
            -1,
        )
        if version_index >= 0:
            console.print(
                f"\n📍 [bold]Position:[/bold] Version {version_index + 1} of {len(versions)}"
            )

            if version_index > 0:
                console.print(f"   ⬆️  Next: {versions[version_index - 1].version_id}")
            if version_index < len(versions) - 1:
                console.print(
                    f"   ⬇️  Previous: {versions[version_index + 1].version_id}"
                )

    except typer.Exit:
        raise
    except Exception as e:
        console.print(f"❌ [red]Error getting version info:[/red] {e}")
        import traceback

        console.print(f"[dim]{traceback.format_exc()}[/dim]")
        raise typer.Exit(1) from None
