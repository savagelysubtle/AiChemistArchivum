# CLI Usage Guide - AIchemist Archivum

Complete guide to using the AIchemist Archivum command-line interface.

## Table of Contents

- [Getting Started](#getting-started)
- [Configuration](#configuration)
- [Ingestion](#ingestion)
- [Search](#search)
- [Tag Management](#tag-management)
- [System Commands](#system-commands)
- [Common Workflows](#common-workflows)

## Getting Started

### First Time Setup

Initialize the system to create necessary directories and database:

```bash
python start.py config init
```

This will:
- Create data directories
- Initialize the SQLite database
- Create default configuration file

### Check System Status

```bash
python start.py status
python start.py info
```

## Configuration

### Initialize System

```bash
# Interactive setup
python start.py config init --interactive

# Non-interactive with custom data directory
python start.py config init --data-dir /path/to/data

# Force reinitialize
python start.py config init --force
```

### View Configuration

```bash
# Show all configuration
python start.py config show

# Show specific section
python start.py config show database

# Export as YAML
python start.py config show --format yaml

# Export as JSON
python start.py config show --format json
```

### Update Configuration

```bash
# Update a configuration value
python start.py config set logging.level DEBUG
python start.py config set ingestion.batch_size 100
python start.py config set database.timeout 60
```

## Ingestion

### Ingest Files

**Single File:**
```bash
# Basic ingestion
python start.py ingest file document.pdf

# With verbose output
python start.py ingest file report.docx --verbose

# Force re-ingestion
python start.py ingest file code.py --force
```

**Folder:**
```bash
# Ingest entire folder
python start.py ingest folder ./documents

# Recursive ingestion
python start.py ingest folder ./project --recursive

# Exclude certain patterns
python start.py ingest folder ./src --exclude "*.pyc" "*.tmp"

# Limit to specific file types
python start.py ingest folder ./code --include "*.py" "*.js"
```

**Batch Ingestion:**
```bash
# Ingest multiple specific files
python start.py ingest batch file1.txt file2.pdf file3.md

# With parallel processing
python start.py ingest batch *.py --parallel 10
```

### Check Ingestion Status

```bash
# View recent ingestions
python start.py ingest status

# View recent ingestions with limit
python start.py ingest recent --limit 20
```

## Search

### Content Search

**Semantic Search:**
```bash
# Basic semantic search
python start.py search content "machine learning algorithms"

# Specify search method
python start.py search content "neural networks" --method semantic

# Limit results
python start.py search content "data science" --max-results 10

# Filter by file type
python start.py search content "python code" --file-types py

# With preview snippets
python start.py search content "API documentation" --preview

# Set minimum relevance score
python start.py search content "database" --min-score 0.7
```

**Full-Text Search:**
```bash
python start.py search content "error handling" --method fulltext
```

**Regex Search:**
```bash
python start.py search content "def \w+\(" --method regex
```

### File Search

```bash
# Search by filename pattern
python start.py search files "*.py"

# Case-sensitive search
python start.py search files "Config" --case-sensitive

# Exact match
python start.py search files "config.yaml" --exact-match

# With details
python start.py search files "test_*" --show-details

# Limit results
python start.py search files "*.md" --max-results 20
```

### Tag-Based Search

```bash
# Find files with any of these tags
python start.py search tags python code

# Find files with ALL specified tags (AND logic)
python start.py search tags python code --match-all

# Limit results
python start.py search tags documentation --max-results 10
```

### Recent Searches

```bash
# View recent search history
python start.py search recent
```

## Tag Management

### Add Tags

```bash
# Add tags to a file
python start.py tag add document.pdf important urgent

# Add multiple tags
python start.py tag add code/script.py python automation testing
```

### Remove Tags

```bash
# Remove specific tags
python start.py tag remove document.pdf urgent

# Remove multiple tags
python start.py tag remove notes.md draft temporary
```

### List Tags

```bash
# List all tags in system
python start.py tag list

# List tags with usage counts
python start.py tag list --counts

# Sort by usage count
python start.py tag list --counts --sort count

# Sort by date
python start.py tag list --sort date

# List tags for specific file
python start.py tag list document.pdf
```

### Create Tags

```bash
# Create a new tag
python start.py tag create urgent

# Create with description
python start.py tag create priority --description "High priority items"

# Create with category
python start.py tag create python-code --category language

# Create with both
python start.py tag create research-paper \
  --description "Academic research papers" \
  --category document-type
```

### Tag Statistics

```bash
# View tag usage statistics
python start.py tag stats
```

## System Commands

### Status and Info

```bash
# Show system status
python start.py status

# Show detailed system information
python start.py info

# Show version
python start.py --version
```

### Help

```bash
# General help
python start.py --help

# Command-specific help
python start.py ingest --help
python start.py search --help
python start.py tag --help
python start.py config --help
```

## Common Workflows

### Workflow 1: Initial Setup and Basic Usage

```bash
# Step 1: Initialize system
python start.py config init

# Step 2: Ingest your documents
python start.py ingest folder ./my-documents --recursive

# Step 3: Search for content
python start.py search content "important topic" --method semantic

# Step 4: Add tags for organization
python start.py tag add document.pdf important reviewed
```

### Workflow 2: Code Project Management

```bash
# Step 1: Ingest code repository
python start.py ingest folder ./src --recursive --include "*.py" "*.js"

# Step 2: Tag code files
python start.py tag add src/main.py python backend core
python start.py tag add src/api.py python api rest

# Step 3: Search code
python start.py search content "authentication" --method fulltext --file-types py

# Step 4: Find all Python files with specific tags
python start.py search tags python api
```

### Workflow 3: Research Paper Organization

```bash
# Step 1: Ingest research papers
python start.py ingest folder ./papers --include "*.pdf"

# Step 2: Tag by topic and status
python start.py tag add papers/ml-paper.pdf machine-learning reviewed important
python start.py tag add papers/nlp-paper.pdf nlp to-read

# Step 3: Search papers by content
python start.py search content "transformer models" --method semantic --file-types pdf

# Step 4: Find papers by status
python start.py search tags reviewed important --match-all

# Step 5: View all research topics
python start.py tag list --counts --sort count
```

### Workflow 4: Content Analysis

```bash
# Step 1: Ingest mixed content
python start.py ingest folder ./content --recursive

# Step 2: Search and tag content
python start.py search content "tutorial" --method semantic | while read file; do
    python start.py tag add "$file" tutorial educational
done

# Step 3: Get statistics
python start.py tag stats
python start.py status
```

## Tips and Best Practices

### Performance

1. **Batch Operations**: Use `ingest batch` with `--parallel` for large file sets
2. **Selective Ingestion**: Use `--include` and `--exclude` patterns to filter files
3. **Index Management**: Re-ingest with `--force` if search results seem stale

### Organization

1. **Tag Naming**: Use consistent, descriptive tag names (lowercase, hyphenated)
2. **Categories**: Create tags with categories for better organization
3. **Hierarchical Tags**: Use patterns like `category-subcategory` for hierarchies

### Search

1. **Method Selection**:
   - `semantic`: Best for concept-based search
   - `fulltext`: Best for exact phrase matching
   - `regex`: Best for pattern-based search
2. **Combine Methods**: Use tags + content search for precise results
3. **Relevance Scores**: Use `--min-score` to filter low-relevance results

### Configuration

1. **Backup Config**: Before major changes, backup your configuration
2. **Custom Paths**: Use `--data-dir` to organize multiple projects separately
3. **Performance Tuning**: Adjust `ingestion.batch_size` based on your hardware

## Troubleshooting

### Common Issues

**Files not found in search:**
```bash
# Re-ingest the files
python start.py ingest file path/to/file --force

# Check if file is in database
python start.py search files "filename"
```

**Configuration errors:**
```bash
# Reinitialize configuration
python start.py config init --force

# Validate configuration
python start.py config show
```

**Database issues:**
```bash
# Check system status
python start.py status

# If needed, reinitialize
python start.py config init --force
```

## Advanced Usage

### Custom Configuration Files

You can modify the configuration file directly at:
- Default: `~/.aichemist-archivum/config/config.yaml`
- Or the location shown in: `python start.py config show`

### Environment Variables

Set `AICHEMIST_ROOT` to use a custom project root directory.

### Scripting

The CLI is designed to be scriptable:

```bash
#!/bin/bash
# Batch process all PDFs in a directory
for pdf in ./papers/*.pdf; do
    python start.py ingest file "$pdf"
    python start.py tag add "$pdf" research pdf
done
```

## Getting Help

- **CLI Help**: `python start.py --help` or `python start.py <command> --help`
- **Documentation**: See `docs/ARCHITECTURE.md` for technical details
- **Issues**: Report bugs on GitHub

---

*Last Updated: October 2025 - Version 0.1.0*
