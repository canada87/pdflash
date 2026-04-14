"""
Async ingestion queue.

- Accepts PDF paths from the API (upload, reindex) and the watchdog thread.
- Processes one PDF at a time via a single-thread ThreadPoolExecutor so the
  asyncio event loop is never blocked.
- Each ingestion run creates its own SQLite connection (WAL allows concurrent
  readers + one writer without lock contention against the API connection).
- Broadcasts SSE events to subscribed clients on completion or failure.
"""
from __future__ import annotations
import asyncio
import sqlite3
from concurrent.futures import ThreadPoolExecutor

from app.config import Config
from app.db import init_db
from app.ingestion.pipeline import ingest_pdf


class IngestionQueue:
    def __init__(self, config: Config) -> None:
        self._config = config
        self._q: asyncio.Queue[tuple[str, bool]] = asyncio.Queue()
        self._pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="ingest")
        self._task: asyncio.Task | None = None
        self._subs: list[asyncio.Queue] = []
        self._loop: asyncio.AbstractEventLoop | None = None

    async def start(self) -> None:
        self._loop = asyncio.get_running_loop()
        self._task = asyncio.create_task(self._worker(), name="ingest-worker")

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self._pool.shutdown(wait=False)

    async def enqueue(self, pdf_path: str, force: bool = False) -> None:
        """Enqueue from async context (API handlers)."""
        await self._q.put((pdf_path, force))

    def enqueue_from_thread(self, pdf_path: str) -> None:
        """Thread-safe enqueue from watchdog or other non-async code."""
        if self._loop and not self._loop.is_closed():
            self._loop.call_soon_threadsafe(self._q.put_nowait, (pdf_path, False))

    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue()
        self._subs.append(q)
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        try:
            self._subs.remove(q)
        except ValueError:
            pass

    async def _broadcast(self, event: dict) -> None:
        for q in self._subs:
            q.put_nowait(event)

    async def _worker(self) -> None:
        loop = asyncio.get_running_loop()
        while True:
            pdf_path, force = await self._q.get()
            try:
                doc_id = await loop.run_in_executor(
                    self._pool,
                    _ingest_sync,
                    pdf_path,
                    self._config,
                    force,
                )
                await self._broadcast({"type": "doc_ready", "doc_id": doc_id})
            except Exception as exc:
                await self._broadcast(
                    {"type": "doc_failed", "path": pdf_path, "reason": str(exc)}
                )
            finally:
                self._q.task_done()


def _ingest_sync(pdf_path: str, config: Config, force: bool) -> int:
    """
    Runs in a ThreadPoolExecutor worker thread.
    Creates its own SQLite connection so it doesn't share state with the
    main thread's connection.
    """
    conn = sqlite3.connect(config.db_path, check_same_thread=True)
    conn.row_factory = sqlite3.Row
    try:
        return ingest_pdf(pdf_path, config, conn, force=force)
    finally:
        conn.close()
