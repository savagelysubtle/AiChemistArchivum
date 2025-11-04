# Security Policy

AIchemist Archivum takes a **secure-by-design** stance inspired by Electron and gRPC hardening guides.

## Supported Versions

| Version | Supported            |
|---------|----------------------|
| ≤ 0.3.x | ✅ Security fixes     |
| ≥ 0.4.x | 🚧 Active development |

## Reporting a Vulnerability

*Email `security@savagelysubtle.dev` (PGP key in `docs/KEYS.txt`). We reply within 72 h.*

## Threat Model

| Surface            | Control                                                | Notes |
|--------------------|--------------------------------------------------------|-------|
| **Electron UI**    | `contextIsolation: true`, `nodeIntegration: false` :contentReference[oaicite:0]{index=0} | Prevents renderer RCE |
| **Python gRPC**    | Runs as child, non-privileged user; TLS optional | AsyncIO core :contentReference[oaicite:1]{index=1} |
| **JSON Gateway**   | FastAPI with rate-limit middleware, JWT auth | Based on gRPC-Gateway model :contentReference[oaicite:2]{index=2} |
| **Plugins/Scripts**| Sandboxed via entry-point loading; no `exec()` | See `docs/PLUGIN_SDK.md` |

### Back-End Hardening

* **Health Checks**—add `grpcio-health-checking` to expose `/grpc.health.v1.Health/Check` :contentReference[oaicite:3]{index=3}
* **Reflection** for debugging only in dev builds, guarded by `DEBUG` flag :contentReference[oaicite:4]{index=4}

### Front-End Hardening

1. Enable Electron **CSP** meta tag (`script-src 'self';`) :contentReference[oaicite:5]{index=5}
2. Use preload-only IPC; never expose `require` :contentReference[oaicite:6]{index=6}

_Pen-test checklist lives in `docs/SECURITY_BEST_PRACTICES.md`._
