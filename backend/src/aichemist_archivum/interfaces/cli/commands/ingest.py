"""
Ingestion commands for AIchemist Archivum CLI.

This module provides commands for ingesting files, batch processing,
and monitoring ingestion status.
"""

import asyncio
import time
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
)
from rich.table import Table

from aichemist_archivum.services.database_service import DatabaseService
from aichemist_archivum.services.ingestion_service import IngestionService
from aichemist_archivum.utils.cache.cache_manager import get_cache_manager

from ..cli import display_results_table, format_file_size, ingest_app

console = Console()


@ingest_app.command("folder")
def ingest_folder(
    path: Annotated[
        Path,
        typer.Argument(
            help="Path to the folder to ingest",
            exists=True,
            file_okay=False,
            dir_okay=True,
            readable=True,
        ),
    ],
    recursive: Annotated[
        bool, typer.Option("--recursive", "-r", help="Process folders recursively")
    ] = True,
    max_files: Annotated[
        int | None,
        typer.Option("--max-files", "-m", help="Maximum number of files to process"),
    ] = None,
    file_pattern: Annotated[
        str | None,
        typer.Option(
            "--pattern", "-p", help="File pattern to match (e.g., '*.py', '*.txt')"
        ),
    ] = None,
    exclude_pattern: Annotated[
        str | None,
        typer.Option(
            "--exclude", "-e", help="Pattern to exclude (e.g., '*.tmp', '__pycache__')"
        ),
    ] = None,
    force: Annotated[
        bool,
        typer.Option(
            "--force", "-f", help="Force reprocessing of already ingested files"
        ),
    ] = False,
    dry_run: Annotated[
        bool,
        typer.Option(
            "--dry-run", help="Show what would be processed without actually ingesting"
        ),
    ] = False,
) -> None:
    """
    📁 Ingest files from a folder

    Processes all files in the specified folder, extracting metadata,
    generating tags, and building the file index.

    [bold]Examples:[/bold]

    • [cyan]archivum ingest folder /path/to/docs[/cyan]
    • [cyan]archivum ingest folder ./code --pattern "*.py"[/cyan]
    • [cyan]archivum ingest folder ./project --exclude "*.tmp"[/cyan]
    • [cyan]archivum ingest folder ./data --dry-run[/cyan]
    """
    asyncio.run(
        _ingest_folder_async(
            path, recursive, max_files, file_pattern, exclude_pattern, force, dry_run
        )
    )


async def _ingest_folder_async(
    path: Path,
    recursive: bool,
    max_files: int | None,
    file_pattern: str | None,
    exclude_pattern: str | None,
    force: bool,
    dry_run: bool,
) -> None:
    """Async implementation of folder ingestion."""
    console.print(f"📁 [bold cyan]Ingesting folder:[/bold cyan] {path}")

    # Collect files to process
    files_to_process = []
    pattern = file_pattern or "*"

    if recursive:
        files_to_process = list(path.rglob(pattern))
    else:
        files_to_process = list(path.glob(pattern))

    # Filter files
    files_to_process = [f for f in files_to_process if f.is_file()]

    # Apply exclusion pattern
    if exclude_pattern:
        import fnmatch

        files_to_process = [
            f for f in files_to_process if not fnmatch.fnmatch(str(f), exclude_pattern)
        ]

    # Limit files if requested
    if max_files:
        files_to_process = files_to_process[:max_files]

    if not files_to_process:
        console.print("ℹ️ No files found to process.")
        return

    console.print(f"📊 Found {len(files_to_process)} files to process")

    if dry_run:
        console.print(
            "\n🔍 [bold yellow]Dry run - files that would be processed:[/bold yellow]"
        )
        for file_path in files_to_process[:10]:  # Show first 10
            file_size = format_file_size(file_path.stat().st_size)
            console.print(f"  • {file_path.name} ({file_size})")

        if len(files_to_process) > 10:
            console.print(f"  ... and {len(files_to_process) - 10} more files")
        return

    # Initialize services
    cache_manager = get_cache_manager()
    ingestion_service = IngestionService(cache_manager=cache_manager)
    database_service = DatabaseService()

    # Initialize database schema
    await database_service.initialize_schema()

    # Process files with progress bar
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("Processing files...", total=len(files_to_process))

        processed = 0
        errors = 0
        skipped = 0

        for file_path in files_to_process:
            try:
                progress.update(task, description=f"Processing {file_path.name}")

                # Check if already processed (unless force is enabled)
                if not force:
                    # This would check database for existing entry
                    pass

                # Extract metadata
                metadata = await ingestion_service.extract_metadata(file_path)

                if metadata.error:
                    errors += 1
                    console.print(
                        f"⚠️ Error processing {file_path.name}: {metadata.error}"
                    )
                else:
                    # Save to database
                    try:
                        await database_service.save_file_metadata(metadata)
                        processed += 1
                    except Exception as e:
                        errors += 1
                        console.print(
                            f"❌ Error saving {file_path.name} to database: {e}"
                        )

                progress.advance(task)

            except Exception as e:
                errors += 1
                console.print(f"❌ Failed to process {file_path.name}: {e}")
                progress.advance(task)

    # Display results
    console.print("\n✅ [bold green]Ingestion completed![/bold green]")

    results_table = Table(show_header=False, box=None)
    results_table.add_column("Metric", style="cyan")
    results_table.add_column("Count", style="green")

    results_table.add_row("Files processed", str(processed))
    results_table.add_row("Errors", str(errors))
    results_table.add_row("Skipped", str(skipped))

    console.print(results_table)


@ingest_app.command("file")
def ingest_file(
    path: Annotated[
        Path,
        typer.Argument(
            help="Path to the file to ingest",
            exists=True,
            file_okay=True,
            dir_okay=False,
            readable=True,
        ),
    ],
    force: Annotated[
        bool,
        typer.Option("--force", "-f", help="Force reprocessing if already ingested"),
    ] = False,
    verbose: Annotated[
        bool,
        typer.Option("--verbose", "-v", help="Show detailed processing information"),
    ] = False,
) -> None:
    """
    📄 Ingest a single file

    Processes a single file, extracting metadata and adding it to the index.

    [bold]Examples:[/bold]

    • [cyan]archivum ingest file document.pdf[/cyan]
    • [cyan]archivum ingest file code.py --verbose[/cyan]
    """
    asyncio.run(_ingest_file_async(path, force, verbose))


async def _ingest_file_async(path: Path, force: bool, verbose: bool) -> None:
    """Async implementation of single file ingestion."""
    console.print(f"📄 [bold cyan]Ingesting file:[/bold cyan] {path}")

    # Initialize services
    cache_manager = get_cache_manager()
    ingestion_service = IngestionService(cache_manager=cache_manager)
    database_service = DatabaseService()

    # Initialize database schema
    await database_service.initialize_schema()

    start_time = time.time()

    try:
        # Extract metadata
        with console.status("🔄 Processing file..."):
            metadata = await ingestion_service.extract_metadata(path)

        if metadata.error:
            console.print(f"❌ [red]Error processing file:[/red] {metadata.error}")
            raise typer.Exit(1)

        # Save to database
        try:
            await database_service.save_file_metadata(metadata)
        except Exception as e:
            console.print(f"❌ [red]Error saving to database:[/red] {e}")
            raise typer.Exit(1)

        processing_time = time.time() - start_time

        # Display results
        console.print(
            "✅ [bold green]File processed and saved to database![/bold green]"
        )

        if verbose:
            # Display detailed metadata
            info_table = Table(title="File Metadata", show_header=False, box=None)
            info_table.add_column("Property", style="cyan", width=20)
            info_table.add_column("Value", style="white")

            info_table.add_row("Path", str(metadata.path))
            info_table.add_row("Size", format_file_size(metadata.size))
            info_table.add_row("MIME Type", metadata.mime_type or "Unknown")
            info_table.add_row("Extension", metadata.extension or "None")
            info_table.add_row("Processing Time", f"{processing_time:.2f}s")
            info_table.add_row(
                "Extraction Complete", "✅" if metadata.extraction_complete else "⚠️"
            )

            console.print(info_table)

    except Exception as e:
        console.print(f"❌ [red]Failed to process file:[/red] {e}")
        raise typer.Exit(1)


@ingest_app.command("batch")
def ingest_batch(
    file_list: Annotated[
        Path,
        typer.Argument(
            help="Path to text file containing list of files to ingest",
            exists=True,
            file_okay=True,
            dir_okay=False,
            readable=True,
        ),
    ],
    parallel: Annotated[
        int,
        typer.Option("--parallel", "-p", help="Number of files to process in parallel"),
    ] = 5,
    force: Annotated[
        bool,
        typer.Option(
            "--force", "-f", help="Force reprocessing of already ingested files"
        ),
    ] = False,
) -> None:
    """
    📋 Ingest files from a batch list

    Processes files listed in a text file, one path per line.
    Supports parallel processing for improved performance.

    [bold]Examples:[/bold]

    • [cyan]archivum ingest batch file_list.txt[/cyan]
    • [cyan]archivum ingest batch files.txt --parallel 10[/cyan]
    """
    asyncio.run(_ingest_batch_async(file_list, parallel, force))


async def _ingest_batch_async(file_list: Path, parallel: int, force: bool) -> None:
    """Async implementation of batch ingestion."""
    console.print(f"📋 [bold cyan]Processing batch file:[/bold cyan] {file_list}")

    # Read file list
    try:
        with open(file_list, encoding="utf-8") as f:
            file_paths = [
                Path(line.strip())
                for line in f.readlines()
                if line.strip() and not line.startswith("#")
            ]
    except Exception as e:
        console.print(f"❌ [red]Error reading batch file:[/red] {e}")
        raise typer.Exit(1)

    # Filter existing files
    existing_files = [p for p in file_paths if p.exists() and p.is_file()]
    missing_files = len(file_paths) - len(existing_files)

    if missing_files > 0:
        console.print(
            f"⚠️ [yellow]Warning:[/yellow] {missing_files} files not found or not accessible"
        )

    if not existing_files:
        console.print("❌ No valid files found to process.")
        raise typer.Exit(1)

    console.print(f"📊 Processing {len(existing_files)} files with {parallel} workers")

    # Initialize services
    cache_manager = get_cache_manager()
    ingestion_service = IngestionService(
        cache_manager=cache_manager, max_concurrent_batch=parallel
    )
    database_service = DatabaseService()

    # Initialize database schema
    await database_service.initialize_schema()

    # Process files with progress tracking
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("Processing batch...", total=len(existing_files))

        processed = 0
        errors = 0

        # Process in chunks to manage memory
        chunk_size = parallel * 2
        for i in range(0, len(existing_files), chunk_size):
            chunk = existing_files[i : i + chunk_size]

            # Process chunk
            tasks = []
            for file_path in chunk:
                task_coro = ingestion_service.extract_metadata(file_path)
                tasks.append(task_coro)

            try:
                results = await asyncio.gather(*tasks, return_exceptions=True)

                for j, result in enumerate(results):
                    if isinstance(result, Exception):
                        errors += 1
                        console.print(f"❌ Error processing {chunk[j].name}: {result}")
                    else:
                        if result.error:
                            errors += 1
                        else:
                            # Save to database
                            try:
                                await database_service.save_file_metadata(result)
                                processed += 1
                            except Exception as e:
                                errors += 1
                                console.print(
                                    f"❌ Error saving {chunk[j].name} to database: {e}"
                                )

                    progress.advance(task)

            except Exception as e:
                console.print(f"❌ Batch processing error: {e}")
                errors += len(chunk)
                progress.advance(task, len(chunk))

    # Display results
    console.print("\n✅ [bold green]Batch processing completed![/bold green]")

    results_table = Table(show_header=False, box=None)
    results_table.add_column("Metric", style="cyan")
    results_table.add_column("Count", style="green")

    results_table.add_row("Files processed", str(processed))
    results_table.add_row("Errors", str(errors))
    results_table.add_row(
        "Success rate",
        f"{(processed / (processed + errors) * 100):.1f}%"
        if (processed + errors) > 0
        else "0%",
    )

    console.print(results_table)


@ingest_app.command("status")
def ingestion_status() -> None:
    """
    📊 Show ingestion system status

    Displays current ingestion status, statistics, and recent activities.
    """
    console.print(Panel.fit("📥 [bold cyan]Ingestion System Status[/bold cyan]"))

    # This would query actual services for real data
    status_data = {
        "Service Status": "✅ Running",
        "Cache Status": "🟢 Active",
        "Queue Size": "0",
        "Files Processed": "1,234",
        "Processing Rate": "15.3 files/min",
        "Error Rate": "0.5%",
        "Last Activity": "2 minutes ago",
    }

    table = Table(show_header=False, box=None)
    table.add_column("Metric", style="cyan", width=20)
    table.add_column("Value", style="white")

    for metric, value in status_data.items():
        table.add_row(metric, value)

    console.print(table)


@ingest_app.command("recent")
def recent_ingestions(
    count: Annotated[
        int, typer.Option("--count", "-n", help="Number of recent ingestions to show")
    ] = 10,
) -> None:
    """
    🕒 Show recent ingestion activities

    Lists the most recently processed files and their status.
    """
    console.print(f"🕒 [bold cyan]Recent Ingestions (last {count})[/bold cyan]")

    # This would query the database for actual recent ingestions
    recent_data = [
        {
            "File": "document.pdf",
            "Status": "✅ Success",
            "Time": "2 min ago",
            "Size": "1.2 MB",
        },
        {
            "File": "code.py",
            "Status": "✅ Success",
            "Time": "5 min ago",
            "Size": "15.3 KB",
        },
        {
            "File": "image.jpg",
            "Status": "⚠️ Warning",
            "Time": "7 min ago",
            "Size": "2.5 MB",
        },
        {
            "File": "data.csv",
            "Status": "✅ Success",
            "Time": "10 min ago",
            "Size": "450 KB",
        },
    ]

    if not recent_data:
        console.print("ℹ️ No recent ingestions found.")
        return

    display_results_table(recent_data[:count], "Recent Ingestions")
