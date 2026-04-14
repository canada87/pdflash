"""
Watchdog-based file watcher for the PDF directory.

Detects created/moved PDF files and enqueues them for ingestion via the
IngestionQueue's thread-safe method.

Fallback note (PLAN.md §13): if watchdog events stop firing on Windows/WSL,
the startup scan + periodic rescan in main.py covers the gap.
"""
from __future__ import annotations
import os
import time

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer


class _PDFHandler(FileSystemEventHandler):
    def __init__(self, queue) -> None:
        self._queue = queue

    def _handle(self, path: str) -> None:
        if not path.lower().endswith(".pdf"):
            return
        # Brief sleep to let the file finish writing before hashing
        time.sleep(0.5)
        if os.path.isfile(path):
            self._queue.enqueue_from_thread(os.path.abspath(path))

    def on_created(self, event) -> None:
        if not event.is_directory:
            self._handle(event.src_path)

    def on_moved(self, event) -> None:
        if not event.is_directory:
            self._handle(event.dest_path)

    # on_modified intentionally omitted: re-saves of the same file go through
    # the hash-check in pipeline.ingest_pdf, so firing on every write event
    # would just add noise. Explicit reindex is available via the API.


def start_watcher(pdf_dir: str, queue) -> Observer:
    observer = Observer()
    observer.schedule(_PDFHandler(queue), pdf_dir, recursive=True)
    observer.start()
    return observer
