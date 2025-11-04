#!/bin/bash
# AIchemist Archivum - Unix/Linux/macOS Startup Script
# This script provides an easy way to run the AIchemist Archivum CLI on Unix-like systems

set -e  # Exit on any error

echo "🧪 AIchemist Archivum - AI-Driven File Management Platform"
echo "============================================================"

# Check if Python 3 is available
if ! command -v python3 &> /dev/null; then
    if ! command -v python &> /dev/null; then
        echo "❌ Error: Python is not installed or not in PATH"
        echo "Please install Python 3.8 or higher"
        exit 1
    else
        PYTHON_CMD="python"
    fi
else
    PYTHON_CMD="python3"
fi

# Check Python version
PYTHON_VERSION=$($PYTHON_CMD -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
MIN_VERSION="3.8"

if ! $PYTHON_CMD -c "import sys; exit(0 if sys.version_info >= (3, 8) else 1)" 2>/dev/null; then
    echo "❌ Error: Python $MIN_VERSION or higher is required"
    echo "Current version: $PYTHON_VERSION"
    exit 1
fi

# Make the script executable (in case it wasn't)
chmod +x "$0" 2>/dev/null || true

# Run the Python startup script with all arguments
$PYTHON_CMD start.py "$@"
