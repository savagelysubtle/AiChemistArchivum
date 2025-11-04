#!/usr/bin/env python3
"""
🧪 AIchemist Archivum - Startup Script

This script provides an easy way to start the AIchemist Archivum CLI application.
It handles path setup, dependency checking, and provides helpful guidance for first-time users.

Usage:
    python start.py [CLI_ARGS...]

Examples:
    python start.py --help
    python start.py config init
    python start.py ingest folder ./my-documents
"""

import os
import sys
from pathlib import Path


def check_python_version():
    """Check if Python version meets requirements."""
    if sys.version_info < (3, 8):
        print("❌ Error: Python 3.8 or higher is required")
        print(f"Current version: {sys.version}")
        sys.exit(1)


def setup_environment():
    """Set up the Python path for the application."""
    # Get the project root directory
    project_root = Path(__file__).parent.absolute()

    # Check if we should use virtual environment
    venv_path = project_root / "venv"
    if venv_path.exists():
        # We're using a virtual environment, add its site-packages to path
        if os.name == "nt":  # Windows
            site_packages = venv_path / "Lib" / "site-packages"
        else:  # Unix-like
            # Find the site-packages directory (version may vary)
            lib_path = venv_path / "lib"
            if lib_path.exists():
                python_dirs = [
                    d for d in lib_path.iterdir() if d.name.startswith("python")
                ]
                if python_dirs:
                    site_packages = python_dirs[0] / "site-packages"
                else:
                    site_packages = None
            else:
                site_packages = None

        if site_packages and site_packages.exists():
            sys.path.insert(0, str(site_packages))

    # Also add backend/src for development
    backend_src = project_root / "backend" / "src"
    if backend_src.exists():
        sys.path.insert(0, str(backend_src))

    # Set environment variables
    os.environ["PYTHONPATH"] = (
        str(backend_src) + os.pathsep + os.environ.get("PYTHONPATH", "")
    )
    os.environ["AICHEMIST_PROJECT_ROOT"] = str(project_root)

    return project_root, backend_src


def check_dependencies():
    """Check if required dependencies are installed."""
    required_packages = [
        "typer",
        "rich",
        "asyncio",  # Built-in, but check for completeness
    ]

    missing_packages = []

    for package in required_packages:
        if package == "asyncio":
            continue  # Built-in module

        try:
            __import__(package)
        except ImportError:
            missing_packages.append(package)

    if missing_packages:
        print("❌ Missing required dependencies:")
        for package in missing_packages:
            print(f"   - {package}")
        print("\n💡 Install dependencies with:")
        print("   pip install typer rich")
        print("   OR")
        print("   cd backend && pip install -e .")
        return False

    return True


def show_welcome_message():
    """Display welcome message and usage instructions."""
    print("🧪 AIchemist Archivum - AI-Driven File Management Platform")
    print("=" * 60)
    print()


def show_first_time_setup():
    """Show first-time setup instructions."""
    print("🚀 Welcome to AIchemist Archivum!")
    print()
    print("📋 First-time setup instructions:")
    print("1. Install dependencies:")
    print("   cd backend && pip install -e .")
    print()
    print("2. Initialize the system:")
    print("   python start.py config init")
    print()
    print("3. Start ingesting files:")
    print("   python start.py ingest folder /path/to/your/files")
    print()
    print("4. Search and explore:")
    print('   python start.py search content "your query"')
    print()
    print("📚 For help with any command:")
    print("   python start.py --help")
    print("   python start.py <command> --help")
    print()


def check_system_status():
    """Check if the system has been initialized."""
    project_root = Path(__file__).parent

    # Check for common indicators that system is set up
    indicators = [
        project_root / ".aichemist-archivum",
        Path.home() / ".aichemist-archivum",
        project_root / "data",
    ]

    for indicator in indicators:
        if indicator.exists():
            return True

    return False


def run_cli(args):
    """Run the CLI application with the provided arguments."""
    try:
        # Import the CLI application
        from aichemist_archivum.interfaces.cli.cli import cli_app

        # IMPORTANT: Import commands to register them with their apps
        try:
            from aichemist_archivum.interfaces.cli import commands
        except ImportError as e:
            print(f"Warning: Could not import all commands: {e}")
            # Try to at least import config
            try:
                from aichemist_archivum.interfaces.cli.commands import config
            except ImportError:
                pass

        # Override sys.argv to pass arguments to the CLI
        original_argv = sys.argv
        sys.argv = ["archivum"] + args

        try:
            cli_app()
        finally:
            # Restore original argv
            sys.argv = original_argv

    except ImportError as e:
        print("❌ Error importing CLI application:")
        print(f"   {e}")
        print()
        print("💡 This usually means:")
        print("   1. Dependencies are not installed")
        print("   2. The application is not properly set up")
        print()
        print("🔧 Try running:")
        print("   python setup.py")
        print("   OR")
        print("   pip install -e .")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error running CLI: {e}")
        sys.exit(1)


def main():
    """Main entry point for the startup script."""
    # Check Python version
    check_python_version()

    # Set up environment
    project_root, backend_src = setup_environment()

    # Show welcome message
    show_welcome_message()

    # Get command line arguments (skip script name)
    cli_args = sys.argv[1:]

    # Special handling for 'archivum' alias
    if len(cli_args) > 0 and cli_args[0] == "archivum":
        cli_args = cli_args[1:]  # Remove the 'archivum' part

    # If no arguments provided, show help and first-time setup
    if not cli_args:
        if not check_system_status():
            show_first_time_setup()
            return
        else:
            # System is set up, just show help
            cli_args = ["--help"]

    # Check dependencies
    if not check_dependencies():
        print("\n💡 Install dependencies first, then try again.")
        sys.exit(1)

    # Run the CLI with the provided arguments
    run_cli(cli_args)


if __name__ == "__main__":
    main()
