# 🧪 AIchemist Archivum

**AIchemist Archivum** is an AI-driven file-management platform that can: * ingest, tag and version any folder tree (code, docs, media) * query content via embeddings, regex or semantic search * surface relationships, tech-stack graphs and code metrics * expose the same workflows through a CLI, a gRPC 2.0 / JSON API, and a desktop GUI (Electron + React + Vite)

The project follows **Clean Architecture**: `core/` → domain logic | `services/` → workflows | `interfaces/` → delivery (CLI / gRPC / Electron).

--- ## Quick Start (dev) ```bash
### clone + enter monorepo root
git clone https://github.com/savagelysubtle/aichemist-archivum
cd aichemist-archivum

## install Python deps
cd backend
poetry install      # or: pip install -e .
cd ..

## install JS deps
cd electron_app
npm install
cd ..

## run backend + GUI together
npm run dev         # see package.json → "dev"``

Port

Process

Notes

50051

gRPC 2.0 (asyncIO)

full RPC surface

8080

JSON gateway (FastAPI)

optional REST

5173

Vite dev server

hot-reload React

3000

Electron window

auto-opens on dev

* * *

Features
--------

Layer

Highlight

**core/**

asynchronous extractors, `tagging/` classifier, version diff engine

**services/**

ingestion, analysis, notification, versioning

**interfaces/**

`cli/` Typer commands • `grpc/` server + JSON gateway • `electron/` bridge

See **`docs/ARCHITECTURE.md`** for the full breakdown.

* * *

Roadmap
-------

*   **MVP 1** – local ingest + search (CLI)

*   **MVP 2** – gRPC2.0 API & Electron desktop release

*   **MVP 3** – pluggable inference back-ends (local Llama / cloud GPT)

*   **MVP 4** – multi-user Supabase back-end & auth


Detailed milestones live in **`docs/ROADMAP.md`**.
