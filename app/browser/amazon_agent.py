"""Amazon browser agent (headful + human-takeover): drives a REAL visible Chromium
via Playwright to open Amazon and search like a human. When it hits a login,
sign-up, CAPTCHA or bot check, it PAUSES and asks the human to take over in the
opened browser window; once the human finishes and clicks "continue", the agent
resumes automatically.

Why headful + persistent context + stealth: Amazon aggressively blocks headless
automation (returns a blank shell page). A visible browser with a real user-data
profile and stealth patches behaves far more like a human, and — crucially — lets
a person step in for the parts a bot shouldn't do (login / CAPTCHA).

Events yielded (dicts):
    {"type":"step","message":..,"shot":<b64|None>}
    {"type":"needs_human","message":..,"shot":..}   # PAUSE: waiting for the person
    {"type":"result","products":[..],"shot":..}
    {"type":"error","message":..}
    {"type":"done"}

Human-takeover signaling: a module-level registry maps session_id -> threading.Event.
The SSE route creates the event before starting and sets it when the client calls
/browser/continue, unblocking the agent.
"""

from __future__ import annotations

import base64
import random
import threading
import time
from pathlib import Path
from typing import Iterator, Optional

__all__ = ["run_amazon_search", "continue_events", "make_continue_event"]

_AMAZON = "https://www.amazon.com/"
_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
)
# persistent profile dir so cookies/login survive between runs (more human-like)
_PROFILE_DIR = str(Path(__file__).resolve().parent.parent.parent / ".browser_profile")

# session_id -> threading.Event used to resume after human takeover
continue_events: dict[str, threading.Event] = {}


def make_continue_event(session_id: str) -> threading.Event:
    ev = threading.Event()
    continue_events[session_id] = ev
    return ev


def _shot(page) -> Optional[str]:
    try:
        raw = page.screenshot(type="png")
        return base64.b64encode(raw).decode("ascii")
    except Exception:  # noqa: BLE001
        return None


def _human_pause(a: float = 0.25, b: float = 0.7) -> None:
    time.sleep(random.uniform(a, b))


def _page_state(page) -> str:
    """Classify the current page: 'ok' | 'captcha' | 'login' | 'blank'."""
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
    log = ("sign in", "sign-in", "email or mobile", "password", "ap/signin")
    url = ""
    try:
        url = page.url.lower()
    except Exception:  # noqa: BLE001
        url = ""
    if "ap/signin" in url or ("sign in" in body and "password" in body):
        return "login"
    if not body.strip() and not title.strip():
        return "blank"
    return "ok"


def _find_search_box(page):
    for sel in ("#twotabsearchtextbox",
                "input[name='field-keywords']",
                "input[type='text'][id*='search']"):
        el = page.query_selector(sel)
        if el:
            return el
    return None


def _wait_for_human(page, session_id, reason, emit):
    """Emit needs_human and block until the client sets the continue event (or timeout)."""
    emit({"type": "needs_human", "message": reason, "shot": _shot(page)})
    ev = continue_events.get(session_id)
    if ev is None:
        ev = make_continue_event(session_id)
    # wait up to 5 minutes for the person to finish and click continue
    ev.wait(timeout=300)
    ev.clear()


def run_amazon_search(query: str, session_id: str = "default") -> Iterator[dict]:
    """Open Amazon (visible browser) and search for ``query`` like a human, pausing
    for human takeover on login/CAPTCHA. Yields step/needs_human/result events."""
    query = (query or "").strip() or "headphones"
    events: list = []

    def emit(ev):
        events.append(ev)

    try:
        from playwright.sync_api import sync_playwright
    except Exception as exc:  # noqa: BLE001
        yield {"type": "error", "message": f"Playwright not available: {exc}"}
        return

    try:
        from playwright_stealth import Stealth
        _stealth = Stealth()
    except Exception:  # noqa: BLE001
        _stealth = None

    # We run the sync automation inline but yield after each emit by draining a list.
    # To keep it a simple generator, we structure as a sequence of steps and yield
    # the collected events as we go.
    with sync_playwright() as p:
        ctx = None
        try:
            emit({"type": "step", "message": "Launching a real (visible) Chrome window...", "shot": None})
            yield from _drain(events)
            ctx = p.chromium.launch_persistent_context(
                _PROFILE_DIR,
                headless=False,
                channel="chrome",  # use real Chrome if available (best against anti-bot)
                args=["--disable-blink-features=AutomationControlled", "--start-maximized"],
                user_agent=_UA,
                viewport={"width": 1360, "height": 900},
                locale="en-US",
            )
            page = ctx.pages[0] if ctx.pages else ctx.new_page()
            if _stealth is not None:
                try:
                    _stealth.apply_stealth_sync(page)
                except Exception:  # noqa: BLE001
                    pass

            emit({"type": "step", "message": f"Opening {_AMAZON}", "shot": None})
            yield from _drain(events)
            page.goto(_AMAZON, wait_until="domcontentloaded", timeout=60000)
            _human_pause(0.8, 1.6)

            # handle blocking / login / captcha with human takeover, up to 3 rounds
            for _ in range(3):
                state = _page_state(page)
                if state == "ok" and _find_search_box(page):
                    break
                reason = {
                    "captcha": "Amazon shows a CAPTCHA / bot check. Please solve it in the browser window, then click Continue.",
                    "login": "Amazon is asking to sign in. Please log in (or dismiss) in the browser window, then click Continue.",
                    "blank": "Amazon returned a challenge page. Please interact with the browser window if needed, then click Continue.",
                    "ok": "Please complete any step in the browser window, then click Continue.",
                }[state if state in ("captcha", "login", "blank") else "ok"]
                _wait_for_human(page, session_id, reason, emit)
                yield from _drain(events)
                _human_pause(0.5, 1.0)
                try:
                    page.wait_for_load_state("domcontentloaded", timeout=15000)
                except Exception:  # noqa: BLE001
                    pass

            emit({"type": "step", "message": "Amazon is ready. Locating the search box.", "shot": _shot(page)})
            yield from _drain(events)

            box = _find_search_box(page)
            if box is None:
                # let the human help find/click the search box
                _wait_for_human(page, session_id,
                                "I couldn't find the search box automatically. Please click Amazon's search box, then Continue.",
                                emit)
                yield from _drain(events)
                box = _find_search_box(page)

            if box is not None:
                bb = box.bounding_box()
                if bb:
                    page.mouse.move(bb["x"] + bb["width"] * 0.3, bb["y"] + bb["height"] / 2, steps=25)
                    _human_pause(0.15, 0.4)
                    page.mouse.click(bb["x"] + bb["width"] * 0.3, bb["y"] + bb["height"] / 2)
                else:
                    box.click()
                emit({"type": "step", "message": "Clicked the search box.", "shot": _shot(page)})
                yield from _drain(events)
                _human_pause(0.2, 0.5)

                box.fill("")
                for ch in query:
                    box.type(ch, delay=random.uniform(70, 170))
                emit({"type": "step", "message": f'Typed the query: "{query}"', "shot": _shot(page)})
                yield from _drain(events)
                _human_pause(0.3, 0.7)

                box.press("Enter")
                emit({"type": "step", "message": "Pressed Enter to search.", "shot": None})
                yield from _drain(events)
                try:
                    page.wait_for_load_state("domcontentloaded", timeout=45000)
                except Exception:  # noqa: BLE001
                    pass
                _human_pause(0.8, 1.4)

            # after search, may hit captcha again -> human takeover
            if _page_state(page) == "captcha":
                _wait_for_human(page, session_id,
                                "Amazon shows a CAPTCHA after searching. Please solve it, then click Continue.",
                                emit)
                yield from _drain(events)

            emit({"type": "step", "message": "Reading the top products from the results.", "shot": _shot(page)})
            yield from _drain(events)

            products = []
            try:
                page.wait_for_selector("div[data-component-type='s-search-result']", timeout=10000)
            except Exception:  # noqa: BLE001
                pass
            cards = page.query_selector_all("div[data-component-type='s-search-result']")[:6]
            for c in cards:
                title_el = c.query_selector("h2 a span") or c.query_selector("h2 span")
                link_el = c.query_selector("h2 a")
                price_el = c.query_selector("span.a-price span.a-offscreen")
                title = (title_el.inner_text().strip() if title_el else "") or ""
                href = ""
                if link_el:
                    href = link_el.get_attribute("href") or ""
                    if href.startswith("/"):
                        href = "https://www.amazon.com" + href
                price = (price_el.inner_text().strip() if price_el else "") or ""
                if title:
                    products.append({"title": title[:150], "price": price, "url": href})

            emit({"type": "result", "products": products, "shot": _shot(page)})
            emit({"type": "done"})
            yield from _drain(events)
        except Exception as exc:  # noqa: BLE001
            emit({"type": "error", "message": f"Browser automation failed: {exc}"})
            yield from _drain(events)
        finally:
            continue_events.pop(session_id, None)
            try:
                if ctx:
                    ctx.close()
            except Exception:  # noqa: BLE001
                pass


def _drain(events: list):
    """Yield and clear all buffered events."""
    while events:
        yield events.pop(0)
