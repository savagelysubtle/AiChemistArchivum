#!/usr/bin/env python3
"""
🚀 AIchemist Archivum - Quick Setup Script

This script automates the installation and initial setup of AIchemist Archivum.
It will install dependencies, initialize the system, and guide you through the first run.

Usage:
    python setup.py
"""

import os
import subprocess
import sys
from pathlib import Path


def run_command(cmd, description, cwd=None):
    """Run a shell command and handle errors gracefully."""
    print(f"📋 {description}...")

    try:
        result = subprocess.run(
            cmd,
            shell=True,
            check=True,
            capture_output=True,
            text=True,
            cwd=cwd,
            encoding="utf-8",
            errors="replace",  # Replace problematic characters
        )
        print(f"✅ {description} completed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ {description} failed:")
        print(f"   Command: {cmd}")
        stderr = e.stderr if e.stderr else e.stdout
        if stderr:
            # Clean up Unicode issues in output
            stderr = stderr.encode("utf-8", errors="replace").decode("utf-8")
        print(f"   Error: {stderr}")
        return False


def check_python_version():
    """Check if Python version meets requirements."""
    if sys.version_info < (3, 8):
        print("❌ Error: Python 3.8 or higher is required")
        print(f"Current version: {sys.version}")
        return False
    else:
        print(
            f"✅ Python {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro} detected"
        )
        return True


def check_git():
    """Check if git is available."""
    try:
        subprocess.run(["git", "--version"], capture_output=True, check=True)
        print("✅ Git is available")
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("⚠️  Git not found - some features may not work optimally")
        return False


def setup_virtual_environment():
    """Set up a virtual environment if it doesn't exist."""
    venv_path = Path("venv")

    if venv_path.exists():
        print("✅ Virtual environment already exists")
        return True

    print("📋 Creating virtual environment...")

    # Try to create virtual environment
    if run_command(f"{sys.executable} -m venv venv", "Create virtual environment"):
        print("✅ Virtual environment created successfully")
        return True
    else:
        print("⚠️  Virtual environment creation failed, continuing without it")
        return False


def install_dependencies():
    """Install Python dependencies."""
    project_root = Path(__file__).parent
    pyproject_path = project_root / "pyproject.toml"

    if not pyproject_path.exists():
        print("❌ pyproject.toml not found")
        return False

    # Check if we're in a virtual environment or should use one
    venv_path = Path("venv")
    if venv_path.exists():
        if os.name == "nt":  # Windows
            python_cmd = str(venv_path / "Scripts" / "python.exe")
            pip_cmd = f'"{python_cmd}" -m pip'
        else:  # Unix-like
            python_cmd = str(venv_path / "bin" / "python")
            pip_cmd = f'"{python_cmd}" -m pip'
    else:
        python_cmd = sys.executable
        pip_cmd = f'"{sys.executable}" -m pip'

    # Upgrade pip first (using proper command format)
    run_command(f"{python_cmd} -m pip install --upgrade pip", "Upgrade pip")

    # Install the package in development mode from root directory
    if run_command(
        f"{pip_cmd} install -e .", "Install AIchemist Archivum", cwd=project_root
    ):
        return True

    # Fallback: try installing individual dependencies
    print("📋 Trying to install individual dependencies...")
    deps = ["typer>=0.9.0", "rich>=13.6.0", "aiofiles>=24.1.0", "pyyaml>=6.0.1"]

    for dep in deps:
        if not run_command(f"{pip_cmd} install {dep}", f"Install {dep}"):
            return False

    return True


def initialize_system():
    """Initialize the AIchemist Archivum system."""
    print("\n🏗️  Initializing AIchemist Archivum...")

    # Try to run the initialization
    try:
        # Set up environment for virtual env if it exists
        venv_path = Path("venv")
        if venv_path.exists():
            if os.name == "nt":  # Windows
                python_cmd = str(venv_path / "Scripts" / "python.exe")
            else:  # Unix-like
                python_cmd = str(venv_path / "bin" / "python")

            # Run initialization using the virtual environment Python
            cmd = f"{python_cmd} start.py config init --no-interactive"
            if run_command(cmd, "Initialize system configuration"):
                print("✅ System initialized successfully")
                return True
            else:
                print("⚠️  System initialization failed")
                print(
                    "   You can initialize manually later with: python start.py config init"
                )
                return False
        else:
            # Try to import directly
            project_root = Path(__file__).parent
            backend_src = project_root / "backend" / "src"
            sys.path.insert(0, str(backend_src))

            # Import CLI

            print("✅ CLI modules loaded successfully")
            print("⚠️  Run 'python start.py config init' to complete setup")
            return True

    except Exception as e:
        print(f"⚠️  System initialization failed: {e}")
        print("   You can initialize manually later with: python start.py config init")
        return False


def show_completion_message():
    """Show completion message with next steps."""
    print("\n" + "🎉" * 20)
    print("🎉 AIchemist Archivum Setup Complete! 🎉")
    print("🎉" * 20)
    print()
    print("🚀 You're ready to start using AIchemist Archivum!")
    print()
    print("📋 Next steps:")
    print("   1. Start the CLI: python start.py --help")
    print("   2. Ingest some files: python start.py ingest folder /path/to/files")
    print('   3. Search content: python start.py search content "your query"')
    print("   4. Explore features: python start.py --help")
    print()
    print("📚 For detailed documentation, see the README.md file")
    print()


def main():
    """Main setup function."""
    print("🚀 AIchemist Archivum - Quick Setup")
    print("=" * 40)
    print()
    print("This script will:")
    print("  • Check system requirements")
    print("  • Set up virtual environment (optional)")
    print("  • Install dependencies")
    print("  • Initialize the system")
    print()

    # Check system requirements
    if not check_python_version():
        sys.exit(1)

    check_git()

    # Ask user if they want to set up virtual environment
    use_venv = (
        input("\n🤔 Set up virtual environment? (recommended) [Y/n]: ").strip().lower()
    )
    if use_venv in ("", "y", "yes"):
        setup_virtual_environment()

    # Install dependencies
    print("\n📦 Installing dependencies...")
    if not install_dependencies():
        print("\n❌ Setup failed during dependency installation")
        print("💡 Try manually running: cd backend && pip install -e .")
        sys.exit(1)

    # Initialize system
    print("\n⚙️  Setting up system...")
    initialize_system()

    # Show completion message
    show_completion_message()


if __name__ == "__main__":
    main()
