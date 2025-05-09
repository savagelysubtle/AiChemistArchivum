"""Analyzes Python code and generates structured summaries."""

import asyncio
import json
import logging
from pathlib import Path

# Use the moved process_file function
from the_aichemist_codex.infrastructure.analysis.technical_analyzer import process_file

# Keep SafeFileHandler if still used by summarize_code
from the_aichemist_codex.infrastructure.utils.common.safety import SafeFileHandler
from the_aichemist_codex.infrastructure.utils.io.async_io import AsyncFileIO

logger = logging.getLogger(__name__)

# Remove unused get_function_metadata if not needed elsewhere
# def get_function_metadata(node):
#     """Extracts function metadata including decorators and return types."""
#     decorators = [d.id for d in node.decorator_list if isinstance(d, ast.Name)]
#     return_type = ast.unparse(node.returns) if node.returns else None
#
#     return {
#         "name": node.name,
#         "args": [arg.arg for arg in node.args.args],
#         "decorators": decorators,
#         "return_type": return_type,
#         "lineno": node.lineno,
#     }

# process_file has been moved to technical_analyzer.py


async def summarize_code(directory: Path):
    """Analyzes Python code in a directory, skipping ignored files."""
    directory = directory.resolve()  # Ensure absolute path

    # Get Python files, skipping ignored ones using SafeFileHandler
    python_files = []
    for path in directory.glob("**/*.py"):
        if SafeFileHandler.should_ignore(path):
            continue  # Skip ignored files and directories
        python_files.append(path)

    if not python_files:
        logger.warning(
            f"No Python files found in {directory} after filtering ignored paths."
        )
        return {}  # Return empty dict if no files

    # Use the process_file from technical_analyzer
    tasks = [process_file(file) for file in python_files]
    results = await asyncio.gather(*tasks, return_exceptions=True)  # Handle errors

    valid_results = {}
    for res in results:
        if isinstance(res, Exception):
            logging.error(f"Error during file processing task: {res}")
        elif isinstance(res, tuple) and len(res) == 2:  # Ensure correct format
            file_path_str, file_data = res
            if file_data.get("error"):
                logging.warning(
                    f"Skipping result for {file_path_str} due to processing error: {file_data.get('summary')}"
                )
            else:
                valid_results[file_path_str] = file_data
        else:
            logging.error(
                f"Invalid result type from process_file(): {type(res)} - {res}"
            )

    return valid_results


async def summarize_project(directory: Path, output_markdown: Path, output_json: Path):
    """Runs the code summarization process and saves multiple output formats."""
    summary = await summarize_code(directory)

    # Log output before saving
    if summary:
        logger.info(
            f"Summarization completed. Sample output: {json.dumps(list(summary.items())[:2], indent=4)}"
        )
    else:
        logger.warning(f"Summarization for {directory} yielded no valid results.")

    if not summary:
        logger.error("No files were analyzed successfully. The summary is empty.")
        # Optionally write empty files or skip writing
        await AsyncFileIO.write(output_json, "{}")
        await AsyncFileIO.write(
            output_markdown, "# Project Code Summary\n\nNo valid files summarized.\n"
        )
        return summary

    # Instead of using the unavailable save_as methods, use AsyncFileIO to save files
    json_str = json.dumps(summary, indent=2)
    await AsyncFileIO.write(output_json, json_str)

    # Create basic markdown output
    md_content = "# Project Code Summary\n\n"
    for file_path, file_data in summary.items():
        # Use Path object for easier manipulation
        relative_path = (
            Path(file_path).relative_to(directory)
            if Path(file_path).is_absolute()
            else Path(file_path)
        )
        md_content += f"## `{relative_path}`\n\n"  # Use relative path in markdown
        md_content += f"**Summary:** {file_data['summary']}\n\n"

        if file_data["functions"]:
            md_content += "### Functions\n\n"
            for func in file_data["functions"]:
                args_str = ", ".join(func["args"])
                md_content += f"- `{func['name']}({args_str})`: {func['docstring']}\n"
            md_content += "\n"

        if file_data["classes"]:
            md_content += "### Classes\n\n"
            for cls in file_data["classes"]:
                md_content += f"- **`{cls['name']}`**: {cls['docstring']}\n"
                if cls["methods"]:
                    md_content += "  - **Methods:**\n"
                    for method in cls["methods"]:
                        m_args_str = ", ".join(method["args"])
                        md_content += f"    - `{method['name']}({m_args_str})`: {method['docstring']}\n"
            md_content += "\n"

        md_content += "---\n\n"

    await AsyncFileIO.write(output_markdown, md_content)

    return summary
