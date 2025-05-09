# Security Best Practices

* **Electron**
  * Disable `nodeIntegration` :contentReference[oaicite:13]{index=13}
  * Enable `contextIsolation` :contentReference[oaicite:14]{index=14}
  * Set `BrowserWindow.webPreferences.sandbox = true`
* **gRPC**
  * Add health service (`grpcio-health-checking`) :contentReference[oaicite:15]{index=15}
  * Enable TLS via `server_credentials` when deploying on WAN
* **Pre-commit**
  * Protect main with Black + Ruff hooks :contentReference[oaicite:16]{index=16}
* **Dependencies**
  * Dependabot alerts enabled; weekly `pip audit`
