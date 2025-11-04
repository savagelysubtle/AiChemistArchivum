# The Aichemist Codex Makefile
#
# This Makefile provides shortcuts for common development tasks

# Python configuration
PYTHON = python
VENV = .venv
VENV_BIN = $(VENV)/bin
VENV_PYTHON = $(VENV_BIN)/python
ifeq ($(OS),Windows_NT)
    VENV_PYTHON = $(VENV)/Scripts/python
    VENV_BIN = $(VENV)/Scripts
endif

# Application variables
PACKAGE_NAME = the_aichemist_codex
SRC_DIR = src
TESTS_DIR = tests
DOCS_DIR = docs

.PHONY: help venv install install-dev clean lint format type-check test docs run check all

help:
	@echo "Aichemist Codex Development Tasks"
	@echo "--------------------------------"
	@echo "make venv         - Create virtual environment"
	@echo "make install      - Install package"
	@echo "make install-dev  - Install package in development mode with dev dependencies"
	@echo "make clean        - Remove build artifacts and cache directories"
	@echo "make lint         - Run linter (ruff)"
	@echo "make format       - Format code (ruff format)"
	@echo "make type-check   - Run type checking (mypy)"
	@echo "make test         - Run tests (pytest)"
	@echo "make docs         - Build documentation"
	@echo "make run          - Run the application"
	@echo "make check        - Run lint, type-check, and test"
	@echo "make all          - Run clean, install-dev, check, and docs"

# Create virtual environment
venv:
	$(PYTHON) -m venv $(VENV)
	@echo "Virtual environment created at $(VENV)"
	@echo "Activate with: source $(VENV_BIN)/activate (Unix) or $(VENV)/Scripts/activate (Windows)"

# Install the package
install:
	$(PYTHON) -m pip install -e .

# Install the package with development dependencies
install-dev:
	$(PYTHON) -m pip install -e ".[dev]"

# Clean build artifacts and cache directories
clean:
	rm -rf build/ dist/ *.egg-info/ .pytest_cache/ .coverage htmlcov/ .ruff_cache/ .mypy_cache/
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type d -name "*.pyc" -delete
	$(MAKE) -C $(DOCS_DIR) clean

# Run lint checks
lint:
	ruff check .

# Format code
format:
	ruff format .

# Run type checking
type-check:
	mypy .

# Run tests
test:
	pytest

# Build documentation
docs:
	$(MAKE) -C $(DOCS_DIR) docsbuild

# Run the application
run:
	python -m $(PACKAGE_NAME)

# Run all checks
check: lint type-check test

# Run clean, install-dev, check, and docs
all: clean install-dev check docs
