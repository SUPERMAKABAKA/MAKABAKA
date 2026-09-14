"""Browser-agent SSE route with human-takeover.

GET  /browser/amazon?q=<query>&sid=<session>
  -> text/event-stream: step | needs_human | result | error | done
POST /browser/continue?sid=<session>
  -> resumes the paused agent after the human finished login/CAPTCHA in the window.

The Playwright SYNC generator runs in a worker thread; events are pushed to an
asyncio.Queue drained by the async SSE generator.
"""

from __future__ import annotations

import asyncio
import json
import threading

from fastapi import APIRouter
from fastapi.responses import JSONResponse, StreamingResponse

from app.browser.amazon_agent import (
    continue_events,
    make_continue_event,
    run_amazon_search,
)

__all__ = ["router"]

router = APIRouter()


@router.post("/browser/continue")
async def browser_continue(sid: str = "default"):
    ev = continue_events.get(sid)
    if ev is not None:
        ev.set()
        return JSONResponse({"ok": True})
    return JSONResponse({"ok": False, "reason": "no active session"}, status_code=404)


@router.get("/browser/amazon")
async def browser_amazon(q: str = "", sid: str = "default"):
    loop = asyncio.get_running_loop()
    queue: asyncio.Queue = asyncio.Queue()
    _SENTINEL = object()
    make_continue_event(sid)  # ready before the worker starts

    def worker():
        try:
            for ev in run_amazon_search(q, sid):
                loop.call_soon_threadsafe(queue.put_nowait, ev)
        except Exception as exc:  # noqa: BLE001
            loop.call_soon_threadsafe(queue.put_nowait, {"type": "error", "message": str(exc)})
        finally:
            loop.call_soon_threadsafe(queue.put_nowait, _SENTINEL)

    async def gen():
        threading.Thread(target=worker, daemon=True).start()
        while True:
            ev = await queue.get()
            if ev is _SENTINEL:
                break
            etype = ev.get("type", "step")
            payload = {k: v for k, v in ev.items() if k != "type"}
            yield f"event: {etype}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"
            if etype == "done":
                break

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
