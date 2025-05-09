# CI Snippets

## GitHub Actions

```yaml
name: CI
on:
  push:
    branches: [ main, dev ]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: '3.12' }
      - run: pip install poetry
      - run: poetry install
      - run: poetry run pytest -q
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: pre-commit/action@v3.0.0
```

### Buf breaking-check

```yaml
- uses: bufbuild/buf-setup-action@v1
- run: buf breaking --against '.git#branch=main'
```
