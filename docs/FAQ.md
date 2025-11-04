# FAQ

### Why gRPC **and** JSON?

Some clients (e.g., cURL, low-code tools) can't speak HTTP/2 or protobuf.
`json_gateway.py` gives them a REST façade without duplicating business logic :contentReference[oaicite:18]{index=18}.

### Can I bundle everything into **one installer**?

Yes. Run PyInstaller to emit `aichemist.exe` then add it to `extraFiles` in
`electron-builder` config :contentReference[oaicite:19]{index=19}. See `docs/DEPLOYMENT.md`.

### Does the project follow **Clean Architecture**?

Yes—entities in `core/` know nothing about frameworks; dependencies flow inward :contentReference[oaicite:20]{index=20}.
