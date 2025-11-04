"""
CLI Commands package for AIchemist Archivum.

This package contains all the command modules for the CLI interface.
"""

# Import all command modules to ensure they register with their respective sub-apps
from . import config

# Try to import other commands - if they fail, we'll just have config
try:
    from . import ingest
except ImportError as e:
    print(f"Warning: Could not import ingest commands: {e}")

try:
    from . import search
except ImportError as e:
    print(f"Warning: Could not import search commands: {e}")

try:
    from . import tag
except ImportError as e:
    print(f"Warning: Could not import tag commands: {e}")

try:
    from . import version
except ImportError as e:
    print(f"Warning: Could not import version commands: {e}")

try:
    from . import analyze
except ImportError as e:
    print(f"Warning: Could not import analyze commands: {e}")

__all__ = ["analyze", "config", "ingest", "search", "tag", "version"]


def main() -> None:
    """Main entry point for the CLI application."""
    from ..cli import cli_app

    cli_app()
