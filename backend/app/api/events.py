"""
Server-Sent Events endpoint.

Clients subscribe to /api/events to receive real-time notifications when
ingestion finishes or fails.  A heartbeat comment is sent every 30 s so
proxies and browsers don't close the connection.
"""
from __future__ import annotations
import asyncio
import json

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from app.state import state

router = APIRouter()


@router.get("/events")
async def sse(request: Request):
    q = state.queue.subscribe()

    async def stream():
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    event = await asyncio.wait_for(q.get(), timeout=30)
                    yield f"data: {json.dumps(event)}\n\n"
                except asyncio.TimeoutError:
                    yield ": heartbeat\n\n"
        finally:
            state.queue.unsubscribe(q)

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # tell Caddy not to buffer SSE
        },
    )
