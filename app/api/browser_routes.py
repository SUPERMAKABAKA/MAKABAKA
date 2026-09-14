"""Persistent browser-session routes (method A).

GET  /browser/session?sid=<id>        -> SSE stream of the session's events
                                         (ready | step | frame | result | needs_human | error | closed)
POST /browser/search?sid=<id>&q=<q>    -> send a search command (reuses the same window)
POST /browser/continue?sid=<id>        -> resume after human takeover
POST /browser/close?sid=<id>           -> close the browser window

The session owns a real Chrome window on its own thread; the SSE route just drains
its event queue. Multiple searches reuse the one window (product tab switching).
"""

from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter
from fastapi.responses import JSONResponse, StreamingResponse

from app.browser.amazon_agent import get_or_create_session, sessions

__all__ = ["router"]

router = APIRouter()


@router.post("/browser/search")
async def browser_search(sid: str = "default", q: str = ""):
    sess = get_or_create_session(sid)
    sess.search(q)
    return JSONResponse({"ok": True})


@router.post("/browser/continue")
async def browser_continue(sid: str = "default"):
    sess = sessions.get(sid)
    if sess is not None:
        sess.resume()
        return JSONResponse({"ok": True})
    return JSONResponse({"ok": False, "reason": "no session"}, status_code=404)


@router.post("/browser/close")
async def browser_close(sid: str = "default"):
    sess = sessions.get(sid)
    if sess is not None:
        sess.close()
    return JSONResponse({"ok": True})


@router.get("/browser/session")
async def browser_session(sid: str = "default", q: str = ""):
    sess = get_or_create_session(sid)
    if q:
        sess.search(q)
    loop = asyncio.get_running_loop()

    async def gen():
        while True:
            # drain the thread-safe queue without blocking the event loop
            try:
                ev = await loop.run_in_executor(None, sess.events.get, True, 30)
            except Exception:  # noqa: BLE001 - queue.Empty on timeout -> heartbeat
                yield ": keep-alive\n\n"
                if not sess.alive:
                    break
                continue
            etype = ev.get("type", "step")
            payload = {k: v for k, v in ev.items() if k != "type"}
            yield f"event: {etype}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"
            if etype == "closed":
                break

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
