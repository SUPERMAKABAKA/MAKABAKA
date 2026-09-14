"""Remote interactive browser routes (method 2).

GET  /browser/session?sid=&w=&h=    -> SSE frame/event stream (viewport w x h)
POST /browser/search?sid=&q=        -> search a product (reuse the session)
POST /browser/viewport?sid=&w=&h=   -> resize the remote viewport to fit the panel
POST /browser/click?sid=&x=&y=      -> forward a click (page coords)
POST /browser/scroll?sid=&dy=       -> forward a wheel scroll
POST /browser/type?sid=&t=          -> type text
POST /browser/key?sid=&k=           -> press a key (Enter/Backspace/...)
POST /browser/continue?sid=         -> resume after human takeover
POST /browser/close?sid=            -> close the remote browser
"""

from __future__ import annotations

import asyncio
import json
import queue as _q

from fastapi import APIRouter
from fastapi.responses import JSONResponse, StreamingResponse

from app.browser.amazon_agent import get_or_create_session, sessions

__all__ = ["router"]

router = APIRouter()


def _sess(sid):
    return sessions.get(sid)


@router.post("/browser/search")
async def browser_search(sid: str = "default", q: str = ""):
    get_or_create_session(sid).search(q)
    return JSONResponse({"ok": True})


@router.post("/browser/viewport")
async def browser_viewport(sid: str = "default", w: int = 900, h: int = 700):
    s = _sess(sid)
    if s: s.set_viewport(w, h)
    return JSONResponse({"ok": bool(s)})


@router.post("/browser/click")
async def browser_click(sid: str = "default", x: float = 0, y: float = 0):
    s = _sess(sid)
    if s: s.click(x, y)
    return JSONResponse({"ok": bool(s)})


@router.post("/browser/scroll")
async def browser_scroll(sid: str = "default", dy: float = 0):
    s = _sess(sid)
    if s: s.scroll(dy)
    return JSONResponse({"ok": bool(s)})


@router.post("/browser/type")
async def browser_type(sid: str = "default", t: str = ""):
    s = _sess(sid)
    if s: s.type_text(t)
    return JSONResponse({"ok": bool(s)})


@router.post("/browser/key")
async def browser_key(sid: str = "default", k: str = ""):
    s = _sess(sid)
    if s: s.key(k)
    return JSONResponse({"ok": bool(s)})


@router.post("/browser/continue")
async def browser_continue(sid: str = "default"):
    s = _sess(sid)
    if s:
        s.resume()
        return JSONResponse({"ok": True})
    return JSONResponse({"ok": False}, status_code=404)


@router.post("/browser/close")
async def browser_close(sid: str = "default"):
    s = _sess(sid)
    if s: s.close()
    return JSONResponse({"ok": True})


@router.get("/browser/session")
async def browser_session(sid: str = "default", w: int = 0, h: int = 0, q: str = ""):
    sess = get_or_create_session(sid)
    if w and h:
        sess.set_viewport(w, h)
    if q:
        sess.search(q)

    async def gen():
        idle = 0
        while True:
            try:
                ev = sess.events.get_nowait()
            except _q.Empty:
                await asyncio.sleep(0.04)
                idle += 1
                if idle >= 500:  # ~20s heartbeat
                    idle = 0
                    yield ": keep-alive\n\n"
                    if not sess.alive:
                        break
                continue
            idle = 0
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
