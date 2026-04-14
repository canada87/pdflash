"""
Module-level singleton that holds shared app state.
Populated by main.py's lifespan handler before the first request.
"""
from __future__ import annotations
import sqlite3
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from watchdog.observers import Observer
    from app.config import Config
    from app.ingestion.queue_worker import IngestionQueue


@dataclass
class AppState:
    config: "Config" = None
    conn: sqlite3.Connection = None
    queue: "IngestionQueue" = None
    watcher: "Observer" = None


state = AppState()
