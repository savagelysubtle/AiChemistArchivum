@echo off
REM AIchemist Archivum - Windows Startup Script
REM This batch file provides an easy way to run the AIchemist Archivum CLI on Windows

echo 🧪 AIchemist Archivum - AI-Driven File Management Platform
echo ============================================================

REM Check if Python is available
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ Error: Python is not installed or not in PATH
    echo Please install Python 3.8 or higher from https://python.org
    pause
    exit /b 1
)

REM Run the Python startup script with all arguments
python start.py %*

REM Pause if there was an error (when run by double-clicking)
if %errorlevel% neq 0 (
    echo.
    echo Press any key to exit...
    pause >nul
)
