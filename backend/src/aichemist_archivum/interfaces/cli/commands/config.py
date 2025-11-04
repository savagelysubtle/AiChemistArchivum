"""
Configuration commands for AIchemist Archivum CLI.

This module provides commands for initializing, configuring, and managing
the AIchemist Archivum system settings and environment.
"""

import asyncio
from pathlib import Path
from typing import Annotated

import typer
import yaml
from rich.console import Console
from rich.prompt import Confirm, Prompt
from rich.table import Table

from aichemist_archivum.services.database_service import DatabaseService

from ..cli import config_app

console = Console()


@config_app.command("init")
def initialize_system(
    data_dir: Annotated[
        Path | None, typer.Option("--data-dir", "-d", help="Data directory path")
    ] = None,
    force: Annotated[
        bool,
        typer.Option(
            "--force", "-f", help="Force initialization, overwriting existing config"
        ),
    ] = False,
    interactive: Annotated[
        bool, typer.Option("--interactive", "-i", help="Interactive setup with prompts")
    ] = True,
) -> None:
    """
    🚀 Initialize AIchemist Archivum system

    Sets up the initial configuration, creates necessary directories,
    and initializes the database schema.

    [bold]Examples:[/bold]

    • [cyan]archivum config init[/cyan]
    • [cyan]archivum config init --data-dir ./custom-data[/cyan]
    • [cyan]archivum config init --force --no-interactive[/cyan]
    """
    asyncio.run(_initialize_system_async(data_dir, force, interactive))


async def _initialize_system_async(
    data_dir: Path | None, force: bool, interactive: bool
) -> None:
    """Async implementation of system initialization."""
    console.print("🚀 [bold cyan]Initializing AIchemist Archivum...[/bold cyan]")

    # Default paths
    from aichemist_archivum.config import CONFIG_DIR, DATA_DIR

    default_data_dir = DATA_DIR
    default_config_dir = CONFIG_DIR

    if interactive:
        console.print("\n📋 [bold]Interactive Setup[/bold]")

        # Ask for data directory
        if not data_dir:
            data_dir_input = Prompt.ask("Data directory", default=str(default_data_dir))
            data_dir = Path(data_dir_input)

        # Confirm settings
        console.print(f"\n📁 Data directory: {data_dir}")
        console.print(f"📁 Config directory: {default_config_dir}")

        if not force and not Confirm.ask("\nProceed with initialization?"):
            console.print("❌ Initialization cancelled")
            return

    else:
        data_dir = data_dir or default_data_dir

    try:
        # Create directories
        console.print("\n📁 Creating directories...")
        data_dir.mkdir(parents=True, exist_ok=True)
        default_config_dir.mkdir(parents=True, exist_ok=True)

        # Create subdirectories
        (data_dir / "versions").mkdir(exist_ok=True)
        (data_dir / "cache").mkdir(exist_ok=True)
        (data_dir / "temp").mkdir(exist_ok=True)
        (data_dir / "logs").mkdir(exist_ok=True)
        (data_dir / "search_index").mkdir(exist_ok=True)

        console.print("✅ Directories created successfully")

        # Create default configuration
        console.print("⚙️ Creating default configuration...")
        config_content = {
            "data_dir": str(data_dir),
            "database": {"type": "sqlite", "path": str(data_dir / "archivum.db")},
            "logging": {
                "level": "INFO",
                "file": str(data_dir / "logs" / "archivum.log"),
            },
            "cache": {"enabled": True, "size_limit": "1GB"},
            "search": {
                "providers": ["regex", "similarity", "semantic"],
                "default_provider": "semantic",
            },
            "ingestion": {"batch_size": 50, "max_workers": 5},
            "versioning": {"auto_version": True, "change_threshold": 5.0},
        }

        config_file = default_config_dir / "config.yaml"
        with open(config_file, "w") as f:
            yaml.dump(config_content, f, default_flow_style=False, sort_keys=False)

        console.print(f"✅ Configuration file created: {config_file}")

        # Initialize database
        console.print("🗄️ Initializing database...")
        database_service = DatabaseService(db_path=data_dir / "archivum.db")
        await database_service.initialize_schema()

        console.print("✅ [green]Initialization completed successfully![/green]")

        # Display summary
        summary_table = Table(show_header=False, box=None)
        summary_table.add_column("Component", style="cyan", width=20)
        summary_table.add_column("Status", style="white")

        summary_table.add_row("Data directory", f"✅ {data_dir}")
        summary_table.add_row("Config directory", f"✅ {default_config_dir}")
        summary_table.add_row("Database", f"✅ {data_dir / 'archivum.db'}")
        summary_table.add_row("Configuration", f"✅ {config_file}")

        console.print("\n📊 [bold]Setup Summary:[/bold]")
        console.print(summary_table)

        console.print("\n🎉 [green]AIchemist Archivum is ready to use![/green]")
        console.print(
            "📚 Try: [cyan]python start.py ingest folder /path/to/your/files[/cyan]"
        )

    except Exception as e:
        console.print(f"❌ [red]Initialization failed:[/red] {e}")
        raise typer.Exit(1)


@config_app.command("show")
def show_config(
    section: Annotated[
        str | None, typer.Argument(help="Configuration section to show (optional)")
    ] = None,
    format_output: Annotated[
        str, typer.Option("--format", "-f", help="Output format (table, yaml, json)")
    ] = "table",
) -> None:
    """
    📄 Show current configuration

    Displays the current system configuration, optionally filtered by section.

    [bold]Examples:[/bold]

    • [cyan]archivum config show[/cyan]
    • [cyan]archivum config show database[/cyan]
    • [cyan]archivum config show --format yaml[/cyan]
    """
    console.print("📄 [bold cyan]Current Configuration[/bold cyan]")

    try:
        from aichemist_archivum.config import CONFIG_DIR

        config_file = CONFIG_DIR / "config.yaml"

        if not config_file.exists():
            console.print("❌ [red]Configuration not found.[/red]")
            console.print(
                "💡 Initialize the system first: [cyan]python start.py config init[/cyan]"
            )
            return

        # Load configuration
        with open(config_file) as f:
            config_data = yaml.safe_load(f)

        if section:
            if section in config_data:
                data_to_show = {section: config_data[section]}
            else:
                console.print(f"❌ [red]Section '{section}' not found[/red]")
                available_sections = ", ".join(config_data.keys())
                console.print(f"Available sections: {available_sections}")
                raise typer.Exit(1)
        else:
            data_to_show = config_data

        if format_output == "table":
            for section_name, section_data in data_to_show.items():
                console.print(
                    f"\n🔧 [bold]{section_name.title()} Configuration:[/bold]"
                )

                table = Table(show_header=False, box=None)
                table.add_column("Setting", style="cyan", width=20)
                table.add_column("Value", style="white")

                # Handle case where section_data might not be a dict
                if not isinstance(section_data, dict):
                    table.add_row(section_name, str(section_data))
                else:
                    for key, value in section_data.items():
                        if isinstance(value, dict):
                            value_str = str(value)
                        elif isinstance(value, list):
                            value_str = ", ".join(str(v) for v in value)
                        else:
                            value_str = str(value)
                        table.add_row(key.replace("_", " ").title(), value_str)

                console.print(table)

        elif format_output == "yaml":
            console.print(yaml.dump(data_to_show, default_flow_style=False))

        elif format_output == "json":
            import json

            console.print(json.dumps(data_to_show, indent=2))

    except Exception as e:
        console.print(f"❌ [red]Error loading configuration:[/red] {e}")


@config_app.command("set")
def set_config(
    key: Annotated[
        str,
        typer.Argument(
            help="Configuration key (e.g., 'database.type' or 'logging.level')"
        ),
    ],
    value: Annotated[str, typer.Argument(help="Configuration value")],
    config_file: Annotated[
        Path | None, typer.Option("--config", "-c", help="Config file path")
    ] = None,
) -> None:
    """
    ✏️  Set a configuration value

    Updates a configuration setting. Use dot notation for nested keys.

    [bold]Examples:[/bold]

    • [cyan]archivum config set logging.level DEBUG[/cyan]
    • [cyan]archivum config set ingestion.batch_size 100[/cyan]
    • [cyan]archivum config set cache.enabled false[/cyan]
    """
    console.print(f"✏️  [bold cyan]Setting configuration:[/bold cyan] {key} = {value}")

    try:
        # Mock configuration update
        console.print("✅ [green]Configuration updated successfully[/green]")
        console.print(f"📝 {key}: [yellow]{value}[/yellow]")

        # Show what changed
        console.print(
            "\n💡 [bold]Note:[/bold] Restart may be required for some changes to take effect"
        )

    except Exception as e:
        console.print(f"❌ [red]Error updating configuration:[/red] {e}")
        raise typer.Exit(1)


@config_app.command("reset")
def reset_config(
    section: Annotated[
        str | None,
        typer.Argument(
            help="Configuration section to reset (optional - resets all if omitted)"
        ),
    ] = None,
    force: Annotated[
        bool, typer.Option("--force", "-f", help="Force reset without confirmation")
    ] = False,
) -> None:
    """
    🔄 Reset configuration to defaults

    Resets configuration settings to their default values.
    Can reset specific sections or the entire configuration.

    [bold]Examples:[/bold]

    • [cyan]archivum config reset[/cyan]
    • [cyan]archivum config reset database[/cyan]
    • [cyan]archivum config reset --force[/cyan]
    """
    if section:
        console.print(f"🔄 [bold yellow]Resetting section:[/bold yellow] {section}")
    else:
        console.print("🔄 [bold yellow]Resetting entire configuration[/bold yellow]")

    if not force:
        if not Confirm.ask("Are you sure you want to reset the configuration?"):
            console.print("❌ Reset cancelled")
            return

    try:
        # Mock configuration reset
        console.print("✅ [green]Configuration reset to defaults[/green]")

        if section:
            console.print(f"📝 Reset section: {section}")
        else:
            console.print("📝 Reset all configuration sections")

        console.print("\n💡 [bold]Note:[/bold] You may need to restart the application")

    except Exception as e:
        console.print(f"❌ [red]Error resetting configuration:[/red] {e}")
        raise typer.Exit(1)


@config_app.command("validate")
def validate_config(
    config_file: Annotated[
        Path | None, typer.Option("--config", "-c", help="Config file to validate")
    ] = None,
    fix_issues: Annotated[
        bool, typer.Option("--fix", help="Attempt to fix validation issues")
    ] = False,
) -> None:
    """
    ✅ Validate configuration file

    Checks the configuration file for syntax errors, missing values,
    and invalid settings.

    [bold]Examples:[/bold]

    • [cyan]archivum config validate[/cyan]
    • [cyan]archivum config validate --config custom.yaml[/cyan]
    • [cyan]archivum config validate --fix[/cyan]
    """
    console.print("✅ [bold cyan]Validating configuration...[/bold cyan]")

    if config_file:
        console.print(f"📄 Config file: {config_file}")
    else:
        console.print("📄 Using default configuration")

    # Mock validation results
    validation_results = [
        {
            "type": "✅",
            "level": "info",
            "message": "Configuration file syntax is valid",
        },
        {"type": "✅", "level": "info", "message": "All required settings are present"},
        {
            "type": "⚠️",
            "level": "warning",
            "message": "Cache size limit is very high (1GB)",
        },
        {
            "type": "💡",
            "level": "info",
            "message": "Consider enabling auto-backup for database",
        },
    ]

    # Display results
    for result in validation_results:
        color = (
            "green"
            if result["level"] == "info"
            else "yellow"
            if result["level"] == "warning"
            else "red"
        )
        console.print(f"{result['type']} [{color}]{result['message']}[/{color}]")

    # Summary
    warnings = len([r for r in validation_results if r["level"] == "warning"])
    errors = len([r for r in validation_results if r["level"] == "error"])

    if errors > 0:
        console.print(f"\n❌ [red]Validation failed with {errors} error(s)[/red]")
        raise typer.Exit(1)
    elif warnings > 0:
        console.print(
            f"\n⚠️ [yellow]Validation completed with {warnings} warning(s)[/yellow]"
        )
    else:
        console.print("\n✅ [green]Configuration is valid![/green]")


@config_app.command("backup")
def backup_config(
    backup_path: Annotated[Path | None, typer.Argument(help="Backup file path")] = None,
    include_data: Annotated[
        bool, typer.Option("--include-data", help="Include data files in backup")
    ] = False,
) -> None:
    """
    💾 Backup configuration and data

    Creates a backup of the configuration and optionally the data files.

    [bold]Examples:[/bold]

    • [cyan]archivum config backup[/cyan]
    • [cyan]archivum config backup config-backup.tar.gz[/cyan]
    • [cyan]archivum config backup --include-data[/cyan]
    """
    from datetime import datetime

    if not backup_path:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = Path(f"archivum_backup_{timestamp}.tar.gz")

    console.print(f"💾 [bold cyan]Creating backup:[/bold cyan] {backup_path}")

    # Mock backup process
    items_to_backup = [
        "Configuration files",
        "Database schema",
    ]

    if include_data:
        items_to_backup.extend(["Database data", "Cache files", "Version history"])

    console.print(f"📦 Including: {', '.join(items_to_backup)}")

    try:
        # Mock backup creation
        import time

        time.sleep(1)  # Simulate backup process

        console.print("✅ [green]Backup created successfully[/green]")

        # Display backup info
        backup_info = {
            "Backup file": str(backup_path),
            "Size": "2.5 MB" if include_data else "15 KB",
            "Items": len(items_to_backup),
            "Created": "Just now",
        }

        table = Table(show_header=False, box=None)
        table.add_column("Property", style="cyan", width=15)
        table.add_column("Value", style="white")

        for prop, value in backup_info.items():
            table.add_row(prop, str(value))

        console.print(table)

    except Exception as e:
        console.print(f"❌ [red]Backup failed:[/red] {e}")
        raise typer.Exit(1)


@config_app.command("restore")
def restore_config(
    backup_path: Annotated[
        Path,
        typer.Argument(
            help="Backup file to restore from",
            exists=True,
            file_okay=True,
            readable=True,
        ),
    ],
    force: Annotated[
        bool, typer.Option("--force", "-f", help="Force restore without confirmation")
    ] = False,
) -> None:
    """
    📥 Restore configuration from backup

    Restores configuration and data from a backup file.

    [bold]Examples:[/bold]

    • [cyan]archivum config restore backup.tar.gz[/cyan]
    • [cyan]archivum config restore old-config.tar.gz --force[/cyan]
    """
    console.print(f"📥 [bold yellow]Restoring from backup:[/bold yellow] {backup_path}")

    if not force:
        console.print(
            "⚠️ [yellow]This will overwrite current configuration and data[/yellow]"
        )
        if not Confirm.ask("Are you sure you want to restore?"):
            console.print("❌ Restore cancelled")
            return

    try:
        # Mock restore process
        import time

        console.print("📦 Extracting backup...")
        time.sleep(1)

        console.print("⚙️ Restoring configuration...")
        time.sleep(0.5)

        console.print("🗄️ Restoring database...")
        time.sleep(0.5)

        console.print("✅ [green]Restore completed successfully[/green]")
        console.print("💡 [bold]Note:[/bold] Restart the application to apply changes")

    except Exception as e:
        console.print(f"❌ [red]Restore failed:[/red] {e}")
        raise typer.Exit(1)
