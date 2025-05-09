# The AIchemist Archivum Codex

An intelligent file management and analysis system with advanced content extraction capabilities.


## Getting Started

### Installation

```bash
pip install -e .
```

### Usage

```python
from aichemist_archivum.core.fs.file_reader import FileReader
from aichemist_archivum.core.ingest.scanner import DirectoryScanner
from aichemist_archivum.core.document_analysis import AnalyzeDocumentsUseCase

# Example usage
reader = FileReader()
scanner = DirectoryScanner()
analyzer = AnalyzeDocumentsUseCase()

# Scan a directory
results = scanner.scan('path/to/directory')

# Read files
documents = reader.read_files(results)

# Analyze documents
analysis_results = analyzer.execute(documents)
```

## Development

### Pre-commit Hooks

The project uses pre-commit hooks to enforce code quality standards. Install and set up pre-commit:

```bash
pip install pre-commit
pre-commit install
```

Run the hooks manually:

```bash
pre-commit run --all-files
```

## License

Proprietary
