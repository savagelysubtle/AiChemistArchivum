# Summary

We adopt an **interface-first** approach: all APIs are defined in `.proto` files, from which we generate both Python and (optionally) TypeScript stubs ([gRPC][1]). The Python backend runs as an **asyncio gRPC server** (leveraging `grpc.aio`) for non-blocking, streaming and unary RPCs ([grpc.github.io][2]). To support REST-style clients, we layer on a **FastAPI** JSON gateway that translates HTTP/2 calls into gRPC requests ([Tyk API Management][3]). This clean separation keeps your **domain/services** logic free of transport concerns and allows both CLI and Electron GUI to consume the same stable API surface.

---

## 1. Protocol Definition (`.proto`)

* **Single source of truth**: Define all service RPCs and messages in `aichemist_archivum.proto` under `interfaces/grpc/proto/`.
* **Example**:

  ```protobuf
  syntax = "proto3";
  package aichemist_archivum;

  service FileManager {
    rpc Ingest(IngestRequest) returns (Empty) {}
    rpc Analyze(AnalyzeRequest) returns (AnalyzeResponse) {}
  }

  message IngestRequest { string path = 1; }
  message AnalyzeRequest { string query = 1; }
  message AnalyzeResponse { repeated string results = 1; }
  ```
* **Benefits**: Language-agnostic API, easy versioning, and automatic client/server stub generation ([gRPC][1]).

---

## 2. Code Generation

* **Python stubs**:

  ```bash
  python -m grpc_tools.protoc \
    -Iinterfaces/grpc/proto \
    --python_out=backend/src \
    --grpc_python_out=backend/src \
    interfaces/grpc/proto/aichemist_archivum.proto
  ```

  This uses `grpcio-tools` to generate both message classes and `grpc.aio` servicer bases ([gRPC][4]).
* **TypeScript stubs (optional)**:
  Use `grpc_tools_node_protoc` with `--ts_out` for front-end clients or Electron renderer code.

---

## 3. AsyncIO gRPC Server (`server.py`)

* **Setup**:

  ```python
  import asyncio
  from grpc import aio
  from aichemist_archivum.interfaces.grpc import aichemist_archivum_pb2_grpc

  from aichemist_archivum.services.ingestion_service import IngestionService

  class FileManagerServicer(aichemist_archivum_pb2_grpc.FileManagerServicer):
      async def Ingest(self, request, context):
          svc = IngestionService()
          svc.ingest(request.path)
          return aichemist_archivum_pb2.Empty()

  async def serve():
      server = aio.server()
      aichemist_archivum_pb2_grpc.add_FileManagerServicer_to_server(
          FileManagerServicer(), server
      )
      server.add_insecure_port('[::]:50051')
      await server.start()
      await server.wait_for_termination()

  if __name__ == "__main__":
      asyncio.run(serve())
  ```
* **Highlights**:

  * Uses `grpc.aio.server()` for non-blocking I/O and streaming support ([grpc.github.io][2]).
  * Streams (unary, server, client, bidi) are all async methods on the servicer ([Stack Overflow][5]).
  * Reflection and health-checking can be registered for debugging and monitoring ([Google Groups][6]).

---

## 4. JSON-over-HTTP Gateway (`json_gateway.py`)

* **FastAPI wrapper**:

  ```python
  from fastapi import FastAPI
  import grpc
  from aichemist_archivum.interfaces.grpc import aichemist_archivum_pb2, aichemist_archivum_pb2_grpc

  def create_app() -> FastAPI:
      app = FastAPI()
      channel = grpc.aio.insecure_channel('localhost:50051')
      stub   = aichemist_archivum_pb2_grpc.FileManagerStub(channel)

      @app.post("/ingest")
      async def ingest(req: dict):
          await stub.Ingest(aichemist_archivum_pb2.IngestRequest(path=req["path"]))
          return {"status": "ok"}

      return app
  ```
* **Combined server** (`server.py`):

  ```python
  import threading, asyncio, uvicorn

  from .json_gateway import create_app
  from .grpc_server import serve as serve_grpc

  def main():
      # Start gRPC in background
      threading.Thread(target=lambda: asyncio.run(serve_grpc()), daemon=True).start()
      # Run JSON gateway
      uvicorn.run(create_app(), host="0.0.0.0", port=8080)

  if __name__ == "__main__":
      main()
  ```
* **Why**: Offers REST for clients that can’t speak gRPC, while sharing the same backend logic ([Tyk API Management][3]).

---

## 5. Client Integration

* **Electron / Renderer**: Use `@grpc/grpc-js` or `grpc-web` to call the gRPC endpoint directly, or hit the JSON gateway for simple HTTP POSTs.
* **CLI**: Can import the generated stubs to call RPCs locally if you prefer, or shell out to `grpcurl` for ad-hoc testing.
* **Testing**: Leverage `grpclib` pure-Python implementation for faster unit tests without requiring the C core ([grpclib.readthedocs.io][7]).

---

## 6. Packaging & Deployment

* **Development**:

  ```bash
  cd backend
  poetry install
  python -m aichemist_archivum.interfaces.grpc.server   # gRPC only
  # or
  python -m aichemist_archivum.interfaces.grpc.json_gateway  # combined HTTP+gRPC
  ```
* **Production**:

  * Bundle Python into a native executable (e.g. PyInstaller) and adjust `main.cjs` spawn command ([YouTube][8]).
  * Use Docker for containerized deployment, exposing ports `50051` (gRPC) and `8080` (REST).
* **CI/CD**: Automate code generation in your build pipeline, lint with `buf` or `protoc`, and run integration tests using `pytest` and `grpc-tools` ([gRPC][4]).

---

## 7. Best Practices & Troubleshooting

* **Thread Safety**: gRPC AsyncIO stubs must be used on the event loop thread they were created on ([grpc.github.io][2]).
* **Blocking Calls**: Offload CPU-bound work using `asyncio.to_thread()` to avoid starving the event loop ([Stack Overflow][5]).
* **Reflection & Health**: Register reflection services for easier debugging via `grpcurl` and implement health checks for orchestration tools ([Google Groups][6]).
* **Versioning**: Use `buf` for linting and breaking-change detection in your `.proto` definitions to keep clients and servers compatible over time ([gRPC][1]).

---

This README should empower your team to understand, extend, and maintain the gRPC2.0 interface—ensuring a robust, scalable API layer that cleanly decouples transport from business logic.

[1]: https://grpc.io/docs/languages/python/basics/?utm_source=chatgpt.com "Basics tutorial | Python - gRPC"
[2]: https://grpc.github.io/grpc/python/grpc_asyncio.html?utm_source=chatgpt.com "gRPC AsyncIO API — gRPC Python 1.71.0 documentation"
[3]: https://tyk.io/docs/5.1/plugins/supported-languages/rich-plugins/grpc/getting-started-python/?utm_source=chatgpt.com "Getting Started: Creating A Python gRPC Server - Tyk.io"
[4]: https://grpc.io/docs/languages/python/quickstart/?utm_source=chatgpt.com "Quick start | Python - gRPC"
[5]: https://stackoverflow.com/questions/53898185/how-can-i-use-grpc-with-asyncio?utm_source=chatgpt.com "How can I use gRPC with asyncio - Stack Overflow"
[6]: https://groups.google.com/g/grpc-io/c/jrwScwlxvSE?utm_source=chatgpt.com "Using the gRPC AsyncIO API in python - Google Groups"
[7]: https://grpclib.readthedocs.io/?utm_source=chatgpt.com "Pure-Python gRPC implementation for asyncio — grpclib ..."
[8]: https://www.youtube.com/watch?v=SDOzb1tt0jU&utm_source=chatgpt.com "Building gRPC Python AsyncIO Stack - Lidi Zheng, Google - YouTube"
