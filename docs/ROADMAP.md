# Roadmap :crystal_ball:

| Version | ETA | Theme | Key Deliverables |
|---------|-----|-------|------------------|
| **0.1.0** | 2025-06 | *"Solo CLI"* | async ingestion, regex + embedding search, local SQLite, Typer CLI |
| **0.2.0** | 2025-07 | *"RPC Ready"* | gRPC2.0 server, protobuf schema v1, FastAPI JSON gateway |
| **0.3.0** | 2025-08 | *"Desktop Alpha"* | Electron bridge, Vite-React UI (browse + search), auto-spawn backend |
| **0.4.0** | 2025-09 | *"Pluggable AI"* | provider interface (OpenAI, Ollama, Llama-cpp), UI model switcher |
| **0.5.0** | 2025-10 | *"Multi-user"* | Supabase auth, per-user vector DB, encrypted client-side storage |
| **1.0.0** | 2025-Q4 | *"Stable"* | CI/CD, docs, plugin SDK, extension marketplace |

### Near-term tasks (0.1.x)

- [ ] Finalise file-type MIME detector
- [ ] Unit tests for `core/tagging`
- [ ] Docker dev-container
- [ ] GitHub Actions (lint + pytest + buf breaking-check)

---

*Roadmap items may shift as user feedback and sponsor priorities evolve.*
