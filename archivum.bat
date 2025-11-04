@echo off
REM AIchemist Archivum - Global CLI Alias
REM This provides a global 'archivum' command that works from any directory

REM Change to the project directory
cd /d "D:\Coding\AiChemistCodex\AiChemistArchivum"

REM Run the start script with all arguments
python start.py %*
