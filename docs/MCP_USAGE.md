# MCP Server Guide - AIchemist Archivum

Complete guide to using the Model Context Protocol (MCP) server for AI agent integration.

## Table of Contents

- [What is MCP?](#what-is-mcp)
- [Quick Start](#quick-start)
- [Configuration](#configuration)
- [Available Tools](#available-tools)
- [Usage Examples](#usage-examples)
- [Architecture](#architecture)
- [Development](#development)
- [Troubleshooting](#troubleshooting)

## What is MCP?

Model Context Protocol (MCP) is a standardized protocol that allows AI agents (like Claude, Cursor AI) to interact with external tools and data sources. The AIchemist Archivum MCP server exposes all core functionality as tools that AI agents can invoke programmatically.

**Think of it as**: Instead of YOU using the CLI commands, an AI agent can use them on your behalf through natural language.

### Use Cases

- **AI-Driven RAG**: Let AI agents search and retrieve information from your indexed documents
- **Automated Organization**: AI can ingest and tag files based on context
- **Knowledge Base Queries**: Ask questions about your documents, AI searches and synthesizes answers
- **Workflow Automation**: Build AI workflows that manage your file knowledge base

## Quick Start

### 1. Install MCP Dependency

```bash
cd backend
uv add mcp
# or
pip install mcp
```

### 2. Configure Cursor

Add to `.cursor/mcp.json` in your project root:

```json
{
  "mcpServers": {
    "aichemist-archivum": {
      "command": "uv",
      "args": [
        "--directory",
        "D:/Coding/AiChemistCodex/AiChemistArchivum/backend",
        "run",
        "python",
        "-m",
        "aichemist_archivum.interfaces.mcp.server"
      ],
      "env": {
        "AICHEMIST_ROOT": "D:/Coding/AiChemistCodex/AiChemistArchivum"
      }
    }
  }
}
```

**Important**: Replace the path with YOUR actual project path!

### 3. Restart Cursor

Completely close and reopen Cursor to load the MCP server.

### 4. Test It

In Cursor chat, try:
```
"Search my ingested documents for authentication examples"
```

## Configuration

### Cursor/VSCode Configuration

The MCP server is configured via `.cursor/mcp.json` (or `.vscode/mcp.json`):

```json
{
  "mcpServers": {
    "aichemist-archivum": {
      "command": "uv",
      "args": [
        "--directory", "/path/to/project/backend",
        "run",
        "python",
        "-m",
        "aichemist_archivum.interfaces.mcp.server"
      ],
      "env": {
        "AICHEMIST_ROOT": "/path/to/project"
      }
    }
  }
}
```

### Alternative: Direct Python

If not using `uv`:

```json
{
  "mcpServers": {
    "aichemist-archivum": {
      "command": "python",
      "args": [
        "-m",
        "aichemist_archivum.interfaces.mcp.server"
      ],
      "cwd": "/path/to/project/backend/src"
    }
  }
}
```

### Claude Desktop Configuration

For Claude Desktop, add to:
- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`
- **Mac**: `~/Library/Application Support/Claude/claude_desktop_config.json`

Same configuration format as above.

## Available Tools

The MCP server exposes 9 tools for AI agents:

### Search Tools

#### 1. `search_semantic`
AI-powered semantic search for finding content by meaning.

**Parameters:**
- `query` (string, required): Natural language search query
- `max_results` (integer, optional): Maximum results to return (default: 10)

**Example:**
```
Agent: "Find documents about machine learning"
→ Calls: search_semantic("machine learning", max_results=10)
```

#### 2. `search_fulltext`
Keyword-based full-text search for exact terms.

**Parameters:**
- `query` (string, required): Keywords to search for
- `max_results` (integer, optional): Maximum results (default: 20)

**Example:**
```
Agent: "Find files containing 'authentication error'"
→ Calls: search_fulltext("authentication error")
```

#### 3. `search_files`
Search for files by filename with fuzzy matching.

**Parameters:**
- `pattern` (string, required): Filename pattern
- `fuzzy` (boolean, optional): Use fuzzy matching (default: true)
- `max_results` (integer, optional): Maximum results (default: 50)

**Example:**
```
Agent: "Find config files"
→ Calls: search_files("config", fuzzy=true)
```

#### 4. `search_by_tags`
Find files by tags.

**Parameters:**
- `tags` (array of strings, required): Tags to search for
- `match_all` (boolean, optional): Require all tags (AND) vs any tag (OR) (default: false)
- `max_results` (integer, optional): Maximum results (default: 50)

**Example:**
```
Agent: "Find Python files tagged as 'production'"
→ Calls: search_by_tags(["python", "production"], match_all=false)
```

### Ingestion Tools

#### 5. `ingest_folder`
Index all files in a folder.

**Parameters:**
- `path` (string, required): Folder path to ingest
- `recursive` (boolean, optional): Process subfolders (default: true)
- `max_files` (integer, optional): Limit number of files
- `file_pattern` (string, optional): File pattern like "*.py"

**Example:**
```
Agent: "Ingest all Python files from ./src"
→ Calls: ingest_folder("./src", file_pattern="*.py")
```

#### 6. `ingest_file`
Index a single file.

**Parameters:**
- `path` (string, required): File path to ingest

**Example:**
```
Agent: "Index the README file"
→ Calls: ingest_file("README.md")
```

### Organization Tools

#### 7. `add_tags`
Add tags to a file.

**Parameters:**
- `file_path` (string, required): Path to file
- `tags` (array of strings, required): Tags to add

**Example:**
```
Agent: "Tag auth.py as 'security' and 'reviewed'"
→ Calls: add_tags("auth.py", ["security", "reviewed"])
```

#### 8. `list_tags`
List all tags with usage counts.

**Parameters:** None

**Example:**
```
Agent: "Show me all tags"
→ Calls: list_tags()
```

### Utility Tools

#### 9. `get_statistics`
Get database statistics.

**Parameters:** None

**Example:**
```
Agent: "How many files are indexed?"
→ Calls: get_statistics()
```

## Usage Examples

### Example 1: Research Assistant

**You**: "Find all documents about authentication and summarize the approaches"

**AI Agent**:
1. Calls `search_semantic("authentication approaches")`
2. Receives: `auth.py`, `security.md`, `login.js`
3. Reads the files (if accessible)
4. Responds: "I found 3 documents about authentication..."

### Example 2: Project Organization

**You**: "Ingest all Python files from ./myproject and tag them appropriately"

**AI Agent**:
1. Calls `ingest_folder("./myproject", file_pattern="*.py")`
2. Receives: "Processed 47 files"
3. Calls `search_by_tags(["python"])` to verify
4. For each file, calls `add_tags(file, ["python", "myproject"])`
5. Responds: "Ingested and tagged 47 Python files"

### Example 3: Knowledge Base Query

**You**: "What error handling patterns do we use in our codebase?"

**AI Agent**:
1. Calls `search_semantic("error handling patterns")`
2. Calls `search_fulltext("try catch exception")`
3. Analyzes results
4. Responds with synthesized answer

### Example 4: Batch Operations

**You**: "Find all files tagged 'deprecated' and list them"

**AI Agent**:
1. Calls `search_by_tags(["deprecated"])`
2. Formats and presents results
3. Asks if you want to take action

## Architecture

### Component Structure

```
┌──────────────────────────────────────┐
│   AI Agent (Cursor/Claude)           │
│   "Natural Language Request"         │
└────────────┬─────────────────────────┘
             │ MCP Protocol (JSON-RPC)
             ↓
┌──────────────────────────────────────┐
│   MCP Server (this module)           │
│   ├── server/mcp_server.py           │
│   │   • Protocol handling            │
│   │   • Resource management          │
│   │   • Tool routing                 │
│   └── tools/tools.py                 │
│       • Tool definitions             │
│       • Service orchestration        │
│       • Result formatting            │
└────────────┬─────────────────────────┘
             │
             ↓
┌──────────────────────────────────────┐
│   Services Layer (existing)          │
│   • IngestionService                 │
│   • SearchEngine                     │
│   • DatabaseService                  │
└──────────────────────────────────────┘
```

### Benefits of Separation

**Server (`server/mcp_server.py`)**:
- Handles MCP protocol specifics
- Manages resources (file listings)
- Routes tool calls
- Server lifecycle management

**Tools (`tools/tools.py`)**:
- Tool definitions and schemas
- Business logic implementations
- Service orchestration
- Result formatting

This separation allows you to:
- Add/modify tools without touching server logic
- Test tools independently
- Evolve protocol handling separately
- Reuse tools in other contexts

## Development

### Adding New Tools

1. **Define tool schema** in `tools/tools.py`:

```python
types.Tool(
    name="my_new_tool",
    description="What it does",
    inputSchema={
        "type": "object",
        "properties": {
            "param": {
                "type": "string",
                "description": "Parameter description"
            }
        },
        "required": ["param"]
    }
)
```

2. **Add handler** to `execute_tool()`:

```python
tool_handlers = {
    # ... existing tools ...
    "my_new_tool": tool_my_new_tool,
}
```

3. **Implement tool**:

```python
async def tool_my_new_tool(args: dict) -> list[types.TextContent]:
    param = args["param"]
    # Do something
    return [types.TextContent(type="text", text="Result")]
```

### Testing Tools

Test standalone:

```bash
cd backend
python -m aichemist_archivum.interfaces.mcp.server
```

The server will wait for JSON-RPC input on stdin.

### Debugging

Enable debug logging:

```python
# In mcp_server.py
logging.basicConfig(level=logging.DEBUG)
```

Check Cursor's output panel for MCP server logs.

## Troubleshooting

### Server Not Starting

**Symptom**: Tools don't appear in Cursor

**Solutions**:
1. Test standalone: `python -m aichemist_archivum.interfaces.mcp.server`
2. Check path in `.cursor/mcp.json` is correct
3. Verify `uv sync` completed successfully
4. Restart Cursor completely (not just reload)
5. Check Cursor output console for errors

### Import Errors

**Symptom**: `ModuleNotFoundError` when starting

**Solutions**:
1. Ensure you're in the right directory
2. Check `PYTHONPATH` includes `backend/src`
3. Install dependencies: `uv sync --all-groups`
4. Verify Python version: `python --version` (should be 3.13+)

### Tools Not Working

**Symptom**: Tools execute but return errors

**Solutions**:
1. Initialize database: `python start.py config init`
2. Ingest some files: `python start.py ingest folder ./docs`
3. Check `data/` directory exists and is writable
4. Check logs in Cursor output panel

### Permission Errors

**Symptom**: "Permission denied" errors

**Solutions**:
```bash
# Ensure data directory is writable
mkdir -p data
chmod -R 755 data
```

### Path Issues

**Symptom**: Server can't find files

**Solutions**:
- Use absolute paths in tool calls
- Set `AICHEMIST_ROOT` environment variable
- Check working directory in MCP config

## Performance Tips

1. **Batch Operations**: Use `ingest_folder` instead of multiple `ingest_file` calls
2. **Limit Results**: Set appropriate `max_results` for searches
3. **File Patterns**: Use specific patterns like `*.py` instead of `*`
4. **Tag Strategy**: Use consistent tagging for faster retrieval

## Security Considerations

- MCP server runs locally with YOUR permissions
- All file access is within your project directory
- No network communication (stdio only)
- AI agent can only use exposed tools
- Review tool definitions before exposing sensitive operations

## Comparison: CLI vs MCP

| Feature | CLI | MCP |
|---------|-----|-----|
| **User** | Human | AI Agent |
| **Interface** | Commands | Function calls |
| **Use Case** | Manual operations | Automated workflows |
| **Speed** | Interactive | Programmatic |
| **Flexibility** | Structured | Contextual |

**Use CLI when**: You want direct control and know exactly what to do

**Use MCP when**: You want AI to figure out what to do based on context

## Next Steps

1. Try the Quick Start above
2. Experiment with different queries in Cursor
3. Read `ARCHITECTURE.md` for system design
4. Add custom tools for your specific workflows
5. Explore MCP specification: https://modelcontextprotocol.io/

---

**Questions?** Check `FAQ.md` or open an issue on GitHub.

