# Testing Strategy

We follow **pyramid testing**: >80 % unit, selective integration, smoke E2E.

## 1. Unit Tests  (`tests/`)

* **pytest** with `pytest-cov` for coverage :contentReference[oaicite:7]{index=7}
* Fixtures mirror core layers; external IO mocked.

```bash
pytest -n auto -q
```

## 2. gRPC Integration

* Use **grpclib**'s in-process server for speed ([grpclib.readthedocs.io][1])
* Health-check verified via generated stub.

## 3. Electron E2E (optional)

* Playwright against packaged `.app` / `.exe`.

## 4. Continuous Quality

| Tool       | Hook                              | Why    |
| ---------- | --------------------------------- | ------ |
| **Ruff**   | `pre-commit` hook  ([GitHub][2])  | lint   |
| **Black**  | `pre-commit` format  ([Black][3]) | style  |
| **buf**    | Breaking-change guard  ([Buf][4]) | .proto |
| **pytest** | PR gate                           | tests  |

See `.pre-commit-config.yaml` example in **docs/CI_SAMPLES.md**.
