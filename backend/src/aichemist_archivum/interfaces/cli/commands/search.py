"""
Search commands for AIchemist Archivum CLI.

This module provides commands for searching content using various methods:
semantic search, regex patterns, filename search, and metadata queries.
"""

import asyncio
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table

from aichemist_archivum.core.search.search_engine import SearchEngine
from aichemist_archivum.services.database_service import DatabaseService

from ..cli import search_app

console = Console()


@search_app.command("content")
def search_content(
    query: Annotated[str, typer.Argument(help="Search query text")],
    method: Annotated[
        str,
        typer.Option(
            "--method", "-m", help="Search method to use (semantic/fulltext/regex)"
        ),
    ] = "semantic",
    max_results: Annotated[
        int,
        typer.Option("--max-results", "-n", help="Maximum number of results to return"),
    ] = 20,
    file_types: Annotated[
        list[str] | None,
        typer.Option("--type", "-t", help="Filter by file types (e.g., pdf, txt, py)"),
    ] = None,
    min_score: Annotated[
        float,
        typer.Option("--min-score", "-s", help="Minimum relevance score (0.0-1.0)"),
    ] = 0.1,
    path_filter: Annotated[
        str | None, typer.Option("--path", "-p", help="Filter results by path pattern")
    ] = None,
    preview: Annotated[
        bool, typer.Option("--preview", help="Show content preview in results")
    ] = False,
) -> None:
    """
    🔍 Search content across all indexed files

    Performs content search using the specified method. Semantic search
    uses AI embeddings for meaning-based matching, while fulltext uses
    traditional keyword matching and regex allows pattern matching.

    [bold]Examples:[/bold]

    • [cyan]archivum search content "machine learning"[/cyan]
    • [cyan]archivum search content "error handling" --method fulltext[/cyan]
    • [cyan]archivum search content "\\d{3}-\\d{3}-\\d{4}" --method regex[/cyan]
    • [cyan]archivum search content "python" --type py --preview[/cyan]
    """
    asyncio.run(
        _search_content_async(
            query, method, max_results, file_types, min_score, path_filter, preview
        )
    )


async def _search_content_async(
    query: str,
    method: str,
    max_results: int,
    file_types: list[str] | None,
    min_score: float,
    path_filter: str | None,
    preview: bool,
) -> None:
    """Async implementation of content search."""
    console.print(f"🔍 [bold cyan]Searching content:[/bold cyan] '{query}'")
    console.print(f"📋 Method: {method} | Max results: {max_results}")

    if file_types:
        console.print(f"📁 File types: {', '.join(file_types)}")

    try:
        # Initialize search engine
        from aichemist_archivum.config import DATA_DIR

        search_engine = SearchEngine(index_dir=DATA_DIR / "search_index")

        # Perform search based on method
        if method == "semantic":
            with console.status("🔄 Searching with semantic search..."):
                result_paths = await search_engine.semantic_search_async(
                    query, top_k=max_results
                )
                results = [
                    {
                        "file": path,
                        "score": 0.9,
                        "snippet": "Semantic match",
                        "type": Path(path).suffix[1:]
                        if Path(path).suffix
                        else "unknown",
                    }
                    for path in result_paths[:max_results]
                ]
        elif method == "fulltext":
            with console.status("🔄 Searching with full-text search..."):
                result_paths = search_engine.full_text_search(query)
                results = [
                    {
                        "file": path,
                        "score": 0.85,
                        "snippet": "Full-text match",
                        "type": Path(path).suffix[1:]
                        if Path(path).suffix
                        else "unknown",
                    }
                    for path in result_paths[:max_results]
                ]
        elif method == "regex":
            with console.status("🔄 Searching with regex..."):
                result_paths = await search_engine.regex_search_async(
                    pattern=query
                )
                # Limit results if max_results is specified
                if max_results:
                    result_paths = result_paths[:max_results]
                results = [
                    {
                        "file": path,
                        "score": 1.0,
                        "snippet": "Regex match",
                        "type": Path(path).suffix[1:]
                        if Path(path).suffix
                        else "unknown",
                    }
                    for path in result_paths[:max_results]
                ]
        else:
            console.print(f"❌ [red]Error:[/red] Unknown search method '{method}'")
            return

        # Filter by file types if specified
        if file_types:
            results = [
                r
                for r in results
                if any(r["file"].endswith(f".{ft}") for ft in file_types)
            ]

        # Filter by minimum score
        results = [r for r in results if r.get("score", 0) >= min_score]

    except Exception as e:
        console.print(f"❌ [red]Search error:[/red] {e}")
        console.print(
            "💡 Make sure files have been ingested first: [cyan]python start.py ingest folder ./path[/cyan]"
        )
        return

    if not results:
        console.print("ℹ️ No results found matching your criteria.")
        return

    console.print(f"\n✅ Found {len(results)} results")

    # Display results
    if preview:
        _display_search_results_with_preview(results)
    else:
        _display_search_results_table(results)


def _display_search_results_table(results: list) -> None:
    """Display search results in a table format."""
    table = Table(title="Search Results", show_header=True, header_style="bold cyan")
    table.add_column("File", style="white", width=30)
    table.add_column("Score", style="green", width=8)
    table.add_column("Type", style="blue", width=8)
    table.add_column("Size", style="yellow", width=10)
    table.add_column("Modified", style="magenta", width=12)

    for result in results:
        table.add_row(
            result["file"],
            f"{result['score']:.2f}",
            result["type"],
            result["size"],
            result["modified"],
        )

    console.print(table)


def _display_search_results_with_preview(results: list) -> None:
    """Display search results with content previews."""
    for i, result in enumerate(results, 1):
        console.print(f"\n[bold cyan]Result {i}:[/bold cyan] {result['file']}")
        console.print(
            f"Score: [green]{result['score']:.2f}[/green] | "
            f"Type: [blue]{result['type']}[/blue] | "
            f"Size: [yellow]{result['size']}[/yellow]"
        )

        # Show snippet with syntax highlighting for code files
        if result["type"] in ["py", "js", "java", "cpp"]:
            syntax = Syntax(
                result["snippet"], result["type"], theme="monokai", line_numbers=False
            )
            console.print(syntax)
        else:
            console.print(Panel(result["snippet"], border_style="dim"))


@search_app.command("files")
def search_files(
    pattern: Annotated[str, typer.Argument(help="Filename pattern or glob")],
    case_sensitive: Annotated[
        bool, typer.Option("--case-sensitive", "-c", help="Case sensitive search")
    ] = False,
    exact_match: Annotated[
        bool, typer.Option("--exact", "-e", help="Exact filename match")
    ] = False,
    max_results: Annotated[
        int,
        typer.Option("--max-results", "-n", help="Maximum number of results to return"),
    ] = 50,
    show_details: Annotated[
        bool, typer.Option("--details", "-d", help="Show detailed file information")
    ] = False,
) -> None:
    """
    📁 Search files by name or pattern

    Searches for files matching the specified name pattern.
    Supports glob patterns and regular expressions.

    [bold]Examples:[/bold]

    • [cyan]archivum search files "*.py"[/cyan]
    • [cyan]archivum search files "test_*" --details[/cyan]
    • [cyan]archivum search files "README" --exact[/cyan]
    • [cyan]archivum search files "Config" --case-sensitive[/cyan]
    """
    asyncio.run(
        _search_files_async(
            pattern, case_sensitive, exact_match, max_results, show_details
        )
    )


async def _search_files_async(
    pattern: str,
    case_sensitive: bool,
    exact_match: bool,
    max_results: int,
    show_details: bool,
) -> None:
    """Async implementation of file search."""
    console.print(f"📁 [bold cyan]Searching files:[/bold cyan] '{pattern}'")

    try:
        # Initialize search engine
        from aichemist_archivum.config import DATA_DIR

        search_engine = SearchEngine(index_dir=DATA_DIR / "search_index")

        # Perform filename search
        with console.status("🔄 Searching filenames..."):
            if exact_match:
                # For exact match, just check the pattern
                result_paths = await search_engine.search_filename_async(pattern)
                results = [p for p in result_paths if Path(p).name == pattern]
            else:
                # Use fuzzy search for partial matches
                if case_sensitive:
                    result_paths = await search_engine.search_filename_async(pattern)
                else:
                    result_paths = await search_engine.fuzzy_search_async(
                        pattern, threshold=60.0
                    )
                results = result_paths

        results = results[:max_results]

    except Exception as e:
        console.print(f"❌ [red]Search error:[/red] {e}")
        console.print(
            "💡 Make sure files have been ingested first: [cyan]python start.py ingest folder ./path[/cyan]"
        )
        return

    if not results:
        console.print("ℹ️ No files found matching the pattern.")
        return

    console.print(f"✅ Found {len(results)} files")

    if show_details:
        table = Table(
            title="File Search Results", show_header=True, header_style="bold cyan"
        )
        table.add_column("Name", style="white", width=25)
        table.add_column("Path", style="blue", width=35)

        for result_path in results:
            result = Path(result_path)
            table.add_row(
                result.name,
                str(result),
            )

        console.print(table)
    else:
        for result_path in results:
            result = Path(result_path)
            console.print(f"  📄 {result.name} - {result}")


@search_app.command("tags")
def search_by_tags(
    tags: Annotated[list[str], typer.Argument(help="Tags to search for")],
    match_all: Annotated[
        bool, typer.Option("--all", help="Require all tags to match (AND logic)")
    ] = False,
    max_results: Annotated[
        int,
        typer.Option("--max-results", "-n", help="Maximum number of results to return"),
    ] = 50,
) -> None:
    """
    🏷️  Search files by tags

    Finds files that have been tagged with the specified tags.
    By default uses OR logic (any tag matches), use --all for AND logic.

    [bold]Examples:[/bold]

    • [cyan]archivum search tags important urgent[/cyan]
    • [cyan]archivum search tags python code --all[/cyan]
    • [cyan]archivum search tags documentation --max-results 10[/cyan]
    """
    asyncio.run(_search_by_tags_async(tags, match_all, max_results))


async def _search_by_tags_async(
    tags: list[str], match_all: bool, max_results: int
) -> None:
    """Async implementation of tag-based search."""
    logic = "AND" if match_all else "OR"
    console.print(
        f"🏷️  [bold cyan]Searching by tags:[/bold cyan] {', '.join(tags)} ({logic})"
    )

    try:
        # Initialize database service
        database_service = DatabaseService()

        # Search files by tags
        with console.status("🔄 Searching by tags..."):
            file_results = await database_service.search_files_by_tags(
                tags, match_all=match_all
            )

        # Limit results
        results = file_results[:max_results]

    except Exception as e:
        console.print(f"❌ [red]Search error:[/red] {e}")
        console.print(
            "💡 Make sure files have been tagged first: [cyan]python start.py tag add file.txt tag1 tag2[/cyan]"
        )
        return

    if not results:
        console.print("ℹ️ No files found with the specified tags.")
        return

    console.print(f"✅ Found {len(results)} files")

    table = Table(
        title="Tag Search Results", show_header=True, header_style="bold cyan"
    )
    table.add_column("File", style="white", width=30)
    table.add_column("Tags", style="blue", width=40)

    for result in results:
        result_tags = result.get("tags", "").split(",") if result.get("tags") else []

        # Highlight matching tags
        tags_display = []
        for tag in result_tags:
            tag = tag.strip()
            if tag in tags:
                tags_display.append(f"[bold green]{tag}[/bold green]")
            else:
                tags_display.append(tag)

        table.add_row(result["filename"], ", ".join(tags_display))

    console.print(table)


@search_app.command("metadata")
def search_metadata(
    query: Annotated[
        str, typer.Argument(help="Metadata query (key:value or key>=value)")
    ],
    max_results: Annotated[
        int,
        typer.Option("--max-results", "-n", help="Maximum number of results to return"),
    ] = 50,
) -> None:
    """
    📊 Search files by metadata properties

    Searches files based on metadata properties like size, type, dates, etc.
    Supports various operators: =, >, <, >=, <=, !=

    [bold]Examples:[/bold]

    • [cyan]archivum search metadata "size>1MB"[/cyan]
    • [cyan]archivum search metadata "type:pdf"[/cyan]
    • [cyan]archivum search metadata "created>=2024-01-01"[/cyan]
    """
    asyncio.run(_search_metadata_async(query, max_results))


async def _search_metadata_async(query: str, max_results: int) -> None:
    """Async implementation of metadata search."""
    console.print(f"📊 [bold cyan]Searching metadata:[/bold cyan] '{query}'")

    # Mock metadata search results
    mock_results = [
        {
            "file": "large_dataset.csv",
            "size": "5.2 MB",
            "type": "csv",
            "created": "2024-01-15",
            "modified": "2024-01-16",
        },
        {
            "file": "presentation.pdf",
            "size": "2.1 MB",
            "type": "pdf",
            "created": "2024-01-10",
            "modified": "2024-01-12",
        },
        {
            "file": "script.py",
            "size": "15.3 KB",
            "type": "python",
            "created": "2024-01-20",
            "modified": "2024-01-20",
        },
    ]

    # Simple query parsing (in real implementation, this would be more sophisticated)
    results = mock_results[:max_results]  # Simplified filtering

    if not results:
        console.print("ℹ️ No files found matching the metadata criteria.")
        return

    console.print(f"✅ Found {len(results)} files")

    table = Table(
        title="Metadata Search Results", show_header=True, header_style="bold cyan"
    )
    table.add_column("File", style="white", width=25)
    table.add_column("Size", style="yellow", width=10)
    table.add_column("Type", style="blue", width=10)
    table.add_column("Created", style="green", width=12)
    table.add_column("Modified", style="magenta", width=12)

    for result in results:
        table.add_row(
            result["file"],
            result["size"],
            result["type"],
            result["created"],
            result["modified"],
        )

    console.print(table)


@search_app.command("recent")
def search_recent(
    days: Annotated[
        int, typer.Option("--days", "-d", help="Number of days to look back")
    ] = 7,
    file_type: Annotated[
        str | None, typer.Option("--type", "-t", help="Filter by file type")
    ] = None,
    max_results: Annotated[
        int,
        typer.Option("--max-results", "-n", help="Maximum number of results to return"),
    ] = 20,
) -> None:
    """
    🕒 Search recently modified or added files

    Finds files that have been modified or added within the specified time period.

    [bold]Examples:[/bold]

    • [cyan]archivum search recent --days 3[/cyan]
    • [cyan]archivum search recent --days 1 --type py[/cyan]
    • [cyan]archivum search recent --days 14 --max-results 50[/cyan]
    """
    console.print(f"🕒 [bold cyan]Searching recent files:[/bold cyan] last {days} days")

    if file_type:
        console.print(f"📁 Filtering by type: {file_type}")

    # Mock recent files
    recent_files = [
        {"file": "updated_script.py", "modified": "2 hours ago", "action": "Modified"},
        {"file": "new_document.md", "modified": "1 day ago", "action": "Created"},
        {"file": "config.json", "modified": "2 days ago", "action": "Modified"},
        {"file": "data_analysis.ipynb", "modified": "3 days ago", "action": "Created"},
    ]

    # Filter by file type if specified
    if file_type:
        recent_files = [f for f in recent_files if f["file"].endswith(f".{file_type}")]

    recent_files = recent_files[:max_results]

    if not recent_files:
        console.print(f"ℹ️ No recent files found in the last {days} days.")
        return

    console.print(f"✅ Found {len(recent_files)} recent files")

    table = Table(title="Recent Files", show_header=True, header_style="bold cyan")
    table.add_column("File", style="white", width=30)
    table.add_column("Action", style="blue", width=10)
    table.add_column("When", style="green", width=15)

    for file_info in recent_files:
        table.add_row(file_info["file"], file_info["action"], file_info["modified"])

    console.print(table)
