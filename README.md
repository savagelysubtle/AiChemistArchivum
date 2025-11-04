# 🧪 AIchemist Archivum

**AIchemist Archivum** is an AI-driven file-management platform that can:
* Ingest, tag and version any folder tree (code, docs, media)
* Query content via embeddings, regex, fuzzy, or semantic search
* Surface relationships, tech-stack graphs and code metrics
* Expose workflows through a CLI with future gRPC 2.0 / JSON API and desktop GUI planned

The project follows **Clean Architecture**: `core/` → domain logic | `services/` → workflows | `interfaces/` → delivery (CLI / gRPC / Electron).

## ⚠️ Current Status: MVP 0.1 - CLI Only

**What's Working:**
- ✅ File ingestion with metadata extraction
- ✅ SQLite database with files, tags, versions
- ✅ Search commands (semantic, full-text, fuzzy, regex, filename, tags)
- ✅ Tag management (add, remove, list, create, stats)
- ✅ Configuration management (init, show, set)
- ✅ Basic test suite

**Not Yet Implemented:**
- ❌ gRPC 2.0 / JSON API server
- ❌ Electron desktop GUI
- ❌ Version management (stubbed but not functional)
- ❌ Analysis commands (stubbed but not functional)

---

## Quick Start

### 🚀 Installation

```bash
# Clone the repository
git clone https://github.com/savagelysubtle/aichemist-archivum
cd aichemist-archivum

# Run the automated setup script
python setup.py

# Start using the CLI
python start.py --help
```

### 💻 Basic Usage

```bash
# 1. Initialize the system
python start.py config init

# 2. Ingest some files
python start.py ingest folder ./documents

# 3. Search your content
python start.py search content "machine learning" --method semantic

# 4. Add tags to organize
python start.py tag add document.pdf important research

# 5. Search by tags
python start.py search tags research important
```

---

## Features

Layer | What's Implemented
------|-------------------
**core/** | Metadata extraction, embedding models, search engine, tag classifier, file system operations
**services/** | Ingestion service (✅), database service (✅), search (✅), tagging (✅)
**interfaces/** | CLI commands (✅) • gRPC server (❌ planned) • Electron GUI (❌ planned)

See **`docs/ARCHITECTURE.md`** for the full breakdown.

### 💻 CLI Commands

**Configuration:**
```bash
python start.py config init          # Initialize system
python start.py config show          # Show configuration
python start.py config set key value # Update config
```

**Ingestion:**
```bash
python start.py ingest folder ./path          # Ingest folder
python start.py ingest file document.pdf      # Ingest single file
python start.py ingest batch file1 file2      # Batch ingest
```

**Search:**
```bash
python start.py search content "query" --method semantic    # Semantic search
python start.py search files "*.py"                         # Filename search
python start.py search tags python code                     # Tag search
```

**Tag Management:**
```bash
python start.py tag add file.txt tag1 tag2    # Add tags
python start.py tag remove file.txt tag1      # Remove tags
python start.py tag list                      # List all tags
python start.py tag stats                     # Show tag statistics
```

**System:**
```bash
python start.py status    # Show system status
python start.py info      # Show system info
```

---

## Testing

```bash
cd backend
pytest tests/ -v --cov=aichemist_archivum
```

---

## Roadmap

- **MVP 0.1** (Current) – Local ingest + search (CLI only) ✅
- **MVP 0.2** – Complete version control and analysis features
- **MVP 1.0** – gRPC 2.0 API server
- **MVP 2.0** – Electron desktop GUI
- **MVP 3.0** – Pluggable inference backends (local Llama / cloud GPT)
- **MVP 4.0** – Multi-user with Supabase backend & auth

Detailed milestones live in **`docs/ROADMAP.md`**.

---

## Documentation

- **`docs/ARCHITECTURE.md`** - System architecture and design
- **`docs/ROADMAP.md`** - Development roadmap and milestones
- **`docs/CLI_USAGE.md`** - Comprehensive CLI usage guide

---

## License

See LICENSE file for details.

## Contributing

Contributions welcome! Please see CONTRIBUTING.md for guidelines.
