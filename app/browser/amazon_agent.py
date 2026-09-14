"""Persistent Amazon browser session (headful, real Chrome) for method A:
one visible, fully-interactive Chrome window per browser-session; the web UI streams
its live screenshots and can switch the search term (recommended products) without
opening new windows. The popped Chrome window is REAL and the user can operate it
(scroll, click, add to cart, log in, solve CAPTCHA).

Architecture:
- ``BrowserSession`` runs a dedicated thread that owns the Playwright browser (sync
  API must stay on one thread). It exposes:
    * a command queue (``search(query)``, ``close()``)
    * an event queue drained by the SSE route
- A registry maps session_id -> BrowserSession.
- The session emits a continuous stream of {"type":"frame","shot":..} screenshots
  (~2 fps) plus step / needs_human / result / error events.
- Human takeover: on login/CAPTCHA it emits needs_human and waits for a continue
  signal (threading.Event) set by /browser/continue.

The frontend flow: after recommendations, open the side panel, list product names
on top; the first product is auto-searched in the real Chrome window; clicking a
different product sends a new ``search`` command reusing the same window.
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

_AMAZON_SEARCH = "https://www.amazon.com/s?k={q}"
_AMAZON_HOME = "https://www.amazon.com/"
_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
)
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
    """Owns one real Chrome window on a dedicated thread; reused across searches."""

    def __init__(self, session_id: str):
        self.session_id = session_id
        self.events: "queue.Queue[dict]" = queue.Queue()
        self.commands: "queue.Queue[tuple]" = queue.Queue()
        self.continue_event = threading.Event()
        self.alive = False
        self._thread: Optional[threading.Thread] = None

    # ---- public API (called from any thread) ----
    def start(self):
        self.alive = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def search(self, query: str):
        self.commands.put(("search", (query or "").strip()))

    def resume(self):
        self.continue_event.set()

    def close(self):
        self.commands.put(("close", None))

    # ---- internals (run on the owning thread) ----
    def _emit(self, ev: dict):
        self.events.put(ev)

    def _shot(self, page) -> Optional[str]:
        try:
            raw = page.screenshot(type="png")
            return base64.b64encode(raw).decode("ascii")
        except Exception:  # noqa: BLE001
            return None

    def _page_state(self, page) -> str:
        try:
            title = (page.title() or "").lower()
        except Exception:  # noqa: BLE001
            title = ""
        body = ""
        try:
            body = (page.inner_text("body") or "").lower()[:600]
        except Exception:  # noqa: BLE001
            body = ""
        cap = ("captcha", "type the characters", "enter the characters",
               "are you a human", "robot check", "automated access", "not a robot")
        if any(m in title or m in body for m in cap):
            return "captcha"
        url = ""
        try:
            url = page.url.lower()
        except Exception:  # noqa: BLE001
            url = ""
        if "ap/signin" in url:
            return "login"
        if not body.strip() and not title.strip():
            return "blank"
        return "ok"

    def _wait_for_human(self, page, reason: str):
        self._emit({"type": "needs_human", "message": reason, "shot": self._shot(page)})
        self.continue_event.clear()
        self.continue_event.wait(timeout=600)
        self.continue_event.clear()

    def _do_search(self, page, query: str):
        query = query or "headphones"
        self._emit({"type": "step", "message": f'Searching Amazon for "{query}"...', "shot": None})
        page.goto(_AMAZON_SEARCH.format(q=query.replace(" ", "+")),
                  wait_until="domcontentloaded", timeout=60000)
        time.sleep(random.uniform(0.8, 1.4))

        for _ in range(3):
            st = self._page_state(page)
            if st == "captcha":
                self._wait_for_human(page, "Amazon shows a CAPTCHA. Please solve it in the Chrome window, then click Continue.")
            elif st == "login":
                self._wait_for_human(page, "Amazon is asking to sign in. Handle it in the Chrome window, then click Continue.")
            elif st == "blank":
                self._wait_for_human(page, "Amazon returned a challenge. Interact with the Chrome window if needed, then click Continue.")
            else:
                break
            try:
                page.wait_for_load_state("domcontentloaded", timeout=15000)
            except Exception:  # noqa: BLE001
                pass

        self._emit({"type": "step", "message": "Results loaded. Reading top products.", "shot": self._shot(page)})

        products = []
        try:
            page.wait_for_selector("div[data-component-type='s-search-result']", timeout=10000)
        except Exception:  # noqa: BLE001
            pass
        cards = page.query_selector_all("div[data-component-type='s-search-result']")[:6]
        for c in cards:
            t = c.query_selector("h2 a span") or c.query_selector("h2 span")
            a = c.query_selector("h2 a")
            pr = c.query_selector("span.a-price span.a-offscreen")
            title = (t.inner_text().strip() if t else "") or ""
            href = ""
            if a:
                href = a.get_attribute("href") or ""
                if href.startswith("/"):
                    href = "https://www.amazon.com" + href
            price = (pr.inner_text().strip() if pr else "") or ""
            if title:
                products.append({"title": title[:150], "price": price, "url": href})
        self._emit({"type": "result", "products": products, "shot": self._shot(page)})

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
                self._emit({"type": "step", "message": "Launching a real Chrome window...", "shot": None})
                try:
                    ctx = p.chromium.launch_persistent_context(
                        _PROFILE_DIR, headless=False, channel="chrome",
                        args=["--disable-blink-features=AutomationControlled", "--start-maximized"],
                        user_agent=_UA, viewport={"width": 1360, "height": 900}, locale="en-US",
                    )
                except Exception:  # noqa: BLE001 - fall back to bundled chromium
                    ctx = p.chromium.launch_persistent_context(
                        _PROFILE_DIR, headless=False,
                        args=["--disable-blink-features=AutomationControlled", "--start-maximized"],
                        user_agent=_UA, viewport={"width": 1360, "height": 900}, locale="en-US",
                    )
                page = ctx.pages[0] if ctx.pages else ctx.new_page()
                if stealth is not None:
                    try:
                        stealth.apply_stealth_sync(page)
                    except Exception:  # noqa: BLE001
                        pass
                page.goto(_AMAZON_HOME, wait_until="domcontentloaded", timeout=60000)
                self._emit({"type": "ready", "message": "Chrome window is open and interactive.", "shot": self._shot(page)})

                last_frame = 0.0
                while self.alive:
                    # process one command if present
                    try:
                        cmd, arg = self.commands.get_nowait()
                    except queue.Empty:
                        cmd, arg = None, None
                    if cmd == "close":
                        break
                    if cmd == "search":
                        try:
                            self._do_search(page, arg)
                        except Exception as exc:  # noqa: BLE001
                            self._emit({"type": "error", "message": f"Search failed: {exc}"})
                    # stream a live frame ~2 fps so the panel mirrors the window
                    now = time.time()
                    if now - last_frame > 0.5:
                        shot = self._shot(page)
                        if shot:
                            self._emit({"type": "frame", "shot": shot})
                        last_frame = now
                    time.sleep(0.12)
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
