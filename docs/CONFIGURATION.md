# Configuration Guide

All runtime settings are defined in **`aichemist_archivum.config.settings`**
(Pydantic `BaseSettings`). Environment variables use the prefix `ARCHIVUM_`.

| Setting | Default | Notes |
|---------|---------|-------|
| `grpc_port` | `50051` | gRPC 2.0 server |
| `rest_port` | `8080`  | JSON gateway |
| `model_provider` | `openai` | or `ollama`, `local_llama.cpp` |
| `log_level` | `INFO` | DictConfig template in `config/logging` |

### Hierarchy of Overrides

1. CLI `--config` flag
2. Env-vars (`ARCHIVUM_GRPC_PORT=6000`)
3. `.env` file (12-factor)
4. `settings.py` defaults

### Secrets

*Never* commit OpenAI keys. Use OS key-store or `.env`.
For production builds (PyInstaller + Electron) embed `.env.enc` + KMS.
