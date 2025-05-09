# Overview

The `interfaces/` folder centralizes all boundary definitions between your AI-driven core/services and external clients, enforcing a clear **Separation of Concerns** so that each interface handles one responsibility—whether it’s a CLI, a gRPC endpoint, a JSON-over-HTTP gateway, or the Electron GUI bridge ([GeeksforGeeks][1]). This layout follows **Clean Architecture** principles by keeping domain logic insulated from delivery mechanisms, making the codebase more maintainable and testable ([Medium][2]).

## Folder Structure

```text
interfaces/
├── cli/
│   └── commands.py
├── grpc/
│   ├── server.py
│   └── json_gateway.py
└── electron/
    ├── main.cjs
    └── preload.cjs
```

* **cli/**: Houses your Typer/Click-based command-line client (entry-point `main`) that invokes services directly.
* **grpc/**: Contains the Python **gRPC2.0** server and an optional JSON gateway for HTTP/2 access, enabling both RPC and RESTful clients ([gRPC][3]).
* **electron/**: Defines the **Electron main** process script that auto-spawns the Python backend and the **preload** script exposing safe APIs to the renderer ([Electron][4], [Electron][5]).

## CLI Interface (`cli/`)

* **Responsibility**: Provide a familiar terminal experience for power users to call ingestion, analysis, notification, and versioning workflows.
* **Entry-point**:

  ```toml
  [project.scripts]
  aichemist = "aichemist_archivum.interfaces.cli.commands:main"
  ```
* **Example**:

  ```bash
  $ aichemist ingest --path /data/docs
  ```

This direct approach is ideal for automation scripts and CI pipelines, keeping user input concerns separate from core logic ([Medium][6]).

## gRPC Interface (`grpc/`)

* **`server.py`** spins up an **asyncio gRPC server** on port `50051`, registering servicers that map RPC methods to your `services/` workflows ([gRPC][3]).
* **`json_gateway.py`** leverages FastAPI (or similar) to translate JSON-over-HTTP/2 calls into gRPC requests, providing a REST-style entrypoint for clients that can’t speak gRPC natively ([Medium][6]).
* **Benefit**: Dual-mode access (RPC + REST) lets you support diverse clients—web apps, mobile apps, and legacy systems—without polluting core code with IO concerns ([microservices.io][7]).

## Electron Bridge (`electron/`)

* **`main.cjs`**:

  * **Auto-spawns** the Python gRPC/JSON server on startup via `child_process.spawn` so end users need only click one executable ([Melle Dijkstra][8]).
  * **Creates** a `BrowserWindow` pointed at the Vite dev server (or packaged frontend) for a seamless integration ([Medium][6]).
  * **Cleans up** the Python process on `app.on('will-quit')` to prevent orphaned services.
* **`preload.cjs`**: Uses `contextBridge` to expose only whitelisted RPC methods (e.g., `window.api.ingest(path)`) to the renderer, enforcing security boundaries and preventing direct Node API access from untrusted content ([Electron][5]).

## Running the Interfaces

1. **Dev Startup**:

   ```bash
   npm install               # in electron_app
   cd backend && uv install
   npm run dev               # runs both Python server and Electron GUI via concurrently
   ```
2. **Production**:

   * **Bundle** Python backend (e.g., via PyInstaller) alongside Electron (e.g., using `electron-builder`).
   * Ensure `main.cjs` references the packaged Python binary rather than `python -m ...`.

---

By organizing each delivery mechanism under its own directory and enforcing minimal, well-defined APIs, you maintain a robust, scalable architecture that cleanly separates **how** functionality is accessed from **what** functionality does. This approach not only follows best practices from **Microservices** and **Clean Architecture** patterns ([Medium][9], [GitHub][10]), but also ensures your Electron GUI remains secure, modular, and easy to evolve.

[1]: https://www.geeksforgeeks.org/separation-of-concerns-soc/?utm_source=chatgpt.com "Separation of Concerns (SoC) - GeeksforGeeks"
[2]: https://medium.com/%40saadjaved120/clean-software-design-and-architecture-with-example-8773c89364c2?utm_source=chatgpt.com "Clean software design and architecture with example - Medium"
[3]: https://grpc.io/docs/languages/python/basics/?utm_source=chatgpt.com "Basics tutorial | Python - gRPC"
[4]: https://electronjs.org/docs/latest/tutorial/tutorial-preload?utm_source=chatgpt.com "Using Preload Scripts - Electron"
[5]: https://electronjs.org/docs/latest/api/context-bridge?utm_source=chatgpt.com "contextBridge - Electron"
[6]: https://medium.com/design-microservices-architecture-with-patterns/headless-architecture-with-separated-ui-for-backend-and-frontend-f9789920e112?utm_source=chatgpt.com "Headless Architecture with Separated UI for Backend and Frontend"
[7]: https://microservices.io/patterns/microservices.html?utm_source=chatgpt.com "Pattern: Microservice Architecture"
[8]: https://melledijkstra.github.io/science/electron-grpc-chat?utm_source=chatgpt.com "Electron gRPC Chat | Melle Dijkstra - GitHub Pages"
[9]: https://medium.com/%40nogueira.cc/4-2-layered-architecture-313329082989?utm_source=chatgpt.com "4+2 Layered Architecture. Separation of Concerns Applied to…"
[10]: https://github.com/rcherara/microservice-architecture/blob/master/README.md?utm_source=chatgpt.com "microservice-architecture/README.md at master - GitHub"
