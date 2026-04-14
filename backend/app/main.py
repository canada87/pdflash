"""
FastAPI application entry point.

Run (from the backend/ directory):
    uvicorn app.main:app --reload --port 8000
"""
from __future__ import annotations
import asyncio
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import Config
from app.db import init_db
from app.ingestion.queue_worker import IngestionQueue
from app.ingestion.watcher import start_watcher
from app.state import state

from app.api import bookmarks, docs, events, health, progress, search, tags


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ───────────────────────────────────────────────────────────────
    state.config = Config()

    # Ensure directories exist
    for d in (
        state.config.pdf_dir,
        state.config.cache_dir,
        state.config.covers_dir,
        os.path.join(state.config.data_dir, "uploads_tmp"),
    ):
        os.makedirs(d, exist_ok=True)

    state.conn = init_db(state.config.db_path)

    state.queue = IngestionQueue(state.config)
    await state.queue.start()

    # Scan pdf_dir on startup (pipeline skips already-indexed files)
    asyncio.create_task(_startup_scan())

    # File watcher
    try:
        state.watcher = start_watcher(state.config.pdf_dir, state.queue)
    except Exception as exc:
        # watchdog is best-effort; startup scan + manual reindex cover the gap
        print(f"[warn] watchdog failed to start: {exc}")
        state.watcher = None

    yield  # ← app is running

    # ── Shutdown ──────────────────────────────────────────────────────────────
    if state.watcher:
        state.watcher.stop()
        state.watcher.join(timeout=3)
    await state.queue.stop()
    if state.conn:
        state.conn.close()


async def _startup_scan() -> None:
    pdf_dir = state.config.pdf_dir
    for root, _, files in os.walk(pdf_dir):
        for name in files:
            if name.lower().endswith(".pdf"):
                path = os.path.abspath(os.path.join(root, name))
                await state.queue.enqueue(path)


app = FastAPI(title="pdflash", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Serve pre-rendered cache files ────────────────────────────────────────────
# In production Caddy intercepts /cache/* before it reaches FastAPI.
# In development this route handles it directly.
@app.get("/cache/{path:path}")
async def serve_cache(path: str):
    file_path = os.path.join(state.config.cache_dir, path)
    if not os.path.isfile(file_path):
        raise HTTPException(404)
    return FileResponse(
        file_path,
        headers={"Cache-Control": "public, max-age=31536000, immutable"},
    )


# ── API routers ───────────────────────────────────────────────────────────────
app.include_router(health.router,    prefix="/api")
app.include_router(docs.router,      prefix="/api")
app.include_router(progress.router,  prefix="/api")
app.include_router(search.router,    prefix="/api")
app.include_router(bookmarks.router, prefix="/api")
app.include_router(tags.router,      prefix="/api")
app.include_router(events.router,    prefix="/api")

# ── Serve built frontend (SPA) ────────────────────────────────────────────────
# Active only when the frontend has been built (docker / production).
# In dev, Vite handles this; the route is harmless if static/ doesn't exist.
_static = os.path.join(os.path.dirname(__file__), "..", "static")
if os.path.isdir(_static):
    app.mount("/", StaticFiles(directory=_static, html=True), name="spa")
