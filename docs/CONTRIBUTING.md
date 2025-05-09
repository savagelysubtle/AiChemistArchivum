# Contributing Guidelines

Thank you for considering a PR! :tada:

1. **Fork** → feature branch → PR to `dev`.
2. Follow **Black** (88 cols) & **Ruff** lint rules (`make format`).
3. Run the full test suite: `pytest -n auto`.
4. If you touch `.proto`, run `make proto` to regenerate stubs and commit them.
5. Add or update docs in `docs/` for any new public surface.
6. One feature or fix per PR. Keep commit messages imperative (“Add X”, “Fix Y”).

---

### Local Dev Helpers

```bash
make format        # Black + isort
make lint          # Ruff
make proto         # regenerate gRPC stubs
make test          # pytest with coverage
```
