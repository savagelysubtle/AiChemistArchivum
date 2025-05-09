"""Main entry point for the AIchemist Codex."""

import sys
from pathlib import Path

# Register parent directory in sys.path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from the_aichemist_codex.interfaces.cli.cli import cli_app


def main() -> None:
    """Main entry point."""
    # Run the CLI app
    cli_app()


if __name__ == "__main__":
    main()
