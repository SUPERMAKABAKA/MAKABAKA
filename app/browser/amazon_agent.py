"""Remote interactive Amazon browser (ChatGPT-Operator style, method 2).

A headless Chromium runs on the server; the web side-panel shows its live frames
(JPEG stream) and forwards the user's clicks / scroll / typing / keys, which are
executed on the real page via Playwright. The browser viewport is sized to match
the side-panel so the picture fits it exactly (self-adaptive).

Public surface:
- ``get_or_create_session(sid)`` -> BrowserSession
- BrowserSession commands (thread-safe): ``search(q)``, ``set_viewport(w,h)``,
  ``click(x,y)``, ``scroll(dy)``, ``type_text(s)``, ``key(k)``, ``resume()``, ``close()``
- Events queue drained by the SSE route: {"type":"frame","shot":<b64 jpeg>,"w":..,"h":..}
  plus step / needs_human / result / error / ready / closed.

Frames are JPEG (small) streamed ~6-8 fps for responsiveness.
"""

from __future__ import annotations

import base64
import queue
import random
import threading
import time
from pathlib import Path
from typing import Optional

__all__ = ["get_or_create_session", "sessions", "BrowserSession"]

_AMAZON_HOME = "https://www.amazon.com/"
_AMAZON_SEARCH = "https://www.amazon.com/s?k={q}"
_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")
_PROFILE_DIR = str(Path(__file__).resolve().parent.parent.parent / ".browser_profile")

sessions: dict[str, "BrowserSession"] = {}
_lock = threading.Lock()


def get_or_create_session(session_id: str) -> "BrowserSession":
    with _lock:
        sess = sessions.get(session_id)
        if sess is None or not sess.alive:
            sess = BrowserSession(session_id)
            sessions[session_id] = sess
            sess.start()
        return sess


class BrowserSession:
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.events: "queue.Queue[dict]" = queue.Queue(maxsize=8)
        self.commands: "queue.Queue[tuple]" = queue.Queue()
        self.continue_event = threading.Event()
        self.alive = False
        self.vw = 900
        self.vh = 700
        self._thread: Optional[threading.Thread] = None

    # ---- public (any thread) ----
    def start(self):
        self.alive = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def search(self, q): self.commands.put(("search", (q or "").strip()))
    def set_viewport(self, w, h): self.commands.put(("viewport", (int(w), int(h))))
    def click(self, x, y): self.commands.put(("click", (float(x), float(y))))
    def scroll(self, dy): self.commands.put(("scroll", float(dy)))
    def type_text(self, s): self.commands.put(("type", str(s)))
    def key(self, k): self.commands.put(("key", str(k)))
    def resume(self): self.continue_event.set()
    def close(self): self.commands.put(("close", None))

    # ---- internals (owning thread) ----
    def _emit(self, ev: dict):
        # frames are droppable; keep the queue from growing unbounded
        if ev.get("type") == "frame":
            try:
                self.events.put_nowait(ev)
            except queue.Full:
                try:
                    self.events.get_nowait()
                    self.events.put_nowait(ev)
                except Exception:  # noqa: BLE001
                    pass
        else:
            try:
                self.events.put(ev, timeout=1)
            except Exception:  # noqa: BLE001
                pass

    def _frame(self, page):
        try:
            raw = page.screenshot(type="jpeg", quality=55)
            return base64.b64encode(raw).decode("ascii")
        except Exception:  # noqa: BLE001
            return None

    def _state(self, page) -> str:
        try:
            title = (page.title() or "").lower()
        except Exception:  # noqa: BLE001
            title = ""
        body = ""
        try:
            body = (page.inner_text("body") or "").lower()[:600]
        except Exception:  # noqa: BLE001
            body = ""
        if any(m in title or m in body for m in
               ("captcha", "type the characters", "enter the characters",
                "are you a human", "robot check", "automated access", "not a robot")):
            return "captcha"
        try:
            if "ap/signin" in (page.url or "").lower():
                return "login"
        except Exception:  # noqa: BLE001
            pass
        if not body.strip() and not title.strip():
            return "blank"
        return "ok"

    def _wait_human(self, page, reason):
        self._emit({"type": "needs_human", "message": reason})
        self.continue_event.clear()
        self.continue_event.wait(timeout=600)
        self.continue_event.clear()

    def _do_search(self, page, q):
        q = q or "headphones"
        self._emit({"type": "step", "message": f'Searching Amazon for "{q}"'})
        page.goto(_AMAZON_SEARCH.format(q=q.replace(" ", "+")),
                  wait_until="domcontentloaded", timeout=60000)
        time.sleep(random.uniform(0.6, 1.2))
        for _ in range(3):
            st = self._state(page)
            if st == "captcha":
                self._wait_human(page, "Amazon shows a CAPTCHA. Solve it right here in the panel, then click Continue.")
            elif st == "login":
                self._wait_human(page, "Amazon wants a sign-in. Handle it here, then click Continue.")
            elif st == "blank":
                self._wait_human(page, "Amazon returned a challenge. Interact here if needed, then click Continue.")
            else:
                break
            try:
                page.wait_for_load_state("domcontentloaded", timeout=15000)
            except Exception:  # noqa: BLE001
                pass
        products = []
        try:
            page.wait_for_selector("div[data-component-type='s-search-result']", timeout=10000)
        except Exception:  # noqa: BLE001
            pass
        for c in page.query_selector_all("div[data-component-type='s-search-result']")[:6]:
            t = c.query_selector("h2 a span") or c.query_selector("h2 span")
            a = c.query_selector("h2 a")
            pr = c.query_selector("span.a-price span.a-offscreen")
            title = (t.inner_text().strip() if t else "") or ""
            href = (a.get_attribute("href") if a else "") or ""
            if href.startswith("/"):
                href = "https://www.amazon.com" + href
            price = (pr.inner_text().strip() if pr else "") or ""
            if title:
                products.append({"title": title[:150], "price": price, "url": href})
        self._emit({"type": "result", "products": products})

    def _apply_viewport(self, page, w, h):
        w = max(360, min(1600, int(w)))
        h = max(360, min(1400, int(h)))
        self.vw, self.vh = w, h
        try:
            page.set_viewport_size({"width": w, "height": h})
        except Exception:  # noqa: BLE001
            pass

    def _run(self):
        try:
            from playwright.sync_api import sync_playwright
        except Exception as exc:  # noqa: BLE001
            self._emit({"type": "error", "message": f"Playwright not available: {exc}"})
            self.alive = False
            return
        try:
            from playwright_stealth import Stealth
            stealth = Stealth()
        except Exception:  # noqa: BLE001
            stealth = None

        with sync_playwright() as p:
            ctx = None
            try:
                self._emit({"type": "step", "message": "Starting remote browser..."})
                launch_kw = dict(
                    headless=True,
                    args=["--disable-blink-features=AutomationControlled"],
                    user_agent=_UA, viewport={"width": self.vw, "height": self.vh}, locale="en-US",
                )
                try:
                    ctx = p.chromium.launch_persistent_context(_PROFILE_DIR, channel="chrome", **launch_kw)
                except Exception:  # noqa: BLE001
                    ctx = p.chromium.launch_persistent_context(_PROFILE_DIR, **launch_kw)
                page = ctx.pages[0] if ctx.pages else ctx.new_page()
                if stealth is not None:
                    try:
                        stealth.apply_stealth_sync(page)
                    except Exception:  # noqa: BLE001
                        pass
                page.goto(_AMAZON_HOME, wait_until="domcontentloaded", timeout=60000)
                self._emit({"type": "ready", "message": "Remote browser ready."})

                last = 0.0
                while self.alive:
                    try:
                        cmd, arg = self.commands.get_nowait()
                    except queue.Empty:
                        cmd, arg = None, None
                    if cmd == "close":
                        break
                    elif cmd == "viewport":
                        self._apply_viewport(page, arg[0], arg[1])
                    elif cmd == "search":
                        try:
                            self._do_search(page, arg)
                        except Exception as exc:  # noqa: BLE001
                            self._emit({"type": "error", "message": f"Search failed: {exc}"})
                    elif cmd == "click":
                        try:
                            page.mouse.click(arg[0], arg[1])
                        except Exception:  # noqa: BLE001
                            pass
                    elif cmd == "scroll":
                        try:
                            page.mouse.wheel(0, arg)
                        except Exception:  # noqa: BLE001
                            pass
                    elif cmd == "type":
                        try:
                            page.keyboard.type(arg, delay=20)
                        except Exception:  # noqa: BLE001
                            pass
                    elif cmd == "key":
                        try:
                            page.keyboard.press(arg)
                        except Exception:  # noqa: BLE001
                            pass
                    # stream frames ~8 fps
                    now = time.time()
                    if now - last > 0.12:
                        f = self._frame(page)
                        if f:
                            self._emit({"type": "frame", "shot": f, "w": self.vw, "h": self.vh})
                        last = now
                    time.sleep(0.02)
            except Exception as exc:  # noqa: BLE001
                self._emit({"type": "error", "message": f"Browser session error: {exc}"})
            finally:
                self.alive = False
                try:
                    if ctx:
                        ctx.close()
                except Exception:  # noqa: BLE001
                    pass
                self._emit({"type": "closed"})
