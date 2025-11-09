# MCP Server Error Fix

## Issue
The MCP server was failing to start with:
```
ModuleNotFoundError: No module named 'aichemist_archivum.core.fs.parsers'
```

## Root Cause
The `backend/src/aichemist_archivum/core/fs/__init__.py` file was trying to import from `.parsers`, which doesn't exist in the `core/fs/` directory.

The `parsers.py` module was moved to `core/parsing/` but the import in `core/fs/__init__.py` wasn't updated.

## Fix Applied
Updated `backend/src/aichemist_archivum/core/fs/__init__.py`:

### Before:
```python
from .parsers import (
    BaseParser,
    TextParser,
    get_parser_for_mime_type,
)
from .rollback import OperationType, RollbackManager, rollback_manager
```

### After:
```python
# Parsers are now in core.parsing, not core.fs
# from ..parsing import (
#     BaseParser,
#     TextParser,
#     get_parser_for_mime_type,
# )

# Note: rollback is in core.versioning, not core.fs
```

Commented out the imports since:
1. Parsers are now in `core.parsing/`
2. Rollback is in `core.versioning/`
3. These imports were causing circular dependencies

## Test the Fix

### 1. Restart the MCP Server
In Cursor, reload the MCP server or restart Cursor completely.

### 2. Check Logs
Look for successful startup:
```
2025-11-04 XX:XX:XX.XXX [info] Starting new stdio process...
2025-11-04 XX:XX:XX.XXX [info] AIchemist Archivum MCP server started
```

### 3. Test a Tool
Try in Cursor chat:
```
"Show me database statistics"
```

Should call `get_statistics()` and return results.

## Next Steps
If you still see errors:
1. Check the MCP output panel in Cursor
2. Try running standalone: `python -m aichemist_archivum.interfaces.mcp.server`
3. Ensure all dependencies are installed: `uv sync`

## Related Files
- `backend/src/aichemist_archivum/core/fs/__init__.py` - Fixed
- `backend/src/aichemist_archivum/core/parsing/parsers.py` - Actual location
- `backend/src/aichemist_archivum/core/versioning/rollback.py` - Actual location


