"""FastAPI 应用入口。

装配 Container、会话仓与 Orchestrator（在 ``app.api.routes`` 内一次性完成），
挂载 ``/chat`` / ``/chat/stream`` 对话路由与 ``/auth`` 鉴权路由，并托管前端
单页界面（``static/index.html``）。
"""

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.auth import router as auth_router
from app.api.browser_routes import router as browser_router
from app.api.routes import router as chat_router

app = FastAPI(title="RAG Multi-Agent Shopping Assistant")

app.include_router(chat_router)
app.include_router(auth_router)
app.include_router(browser_router)

_STATIC_DIR = Path(__file__).parent / "static"

if (_STATIC_DIR / "assets").is_dir():
    app.mount("/assets", StaticFiles(directory=_STATIC_DIR / "assets"), name="assets")


@app.get("/", include_in_schema=False)
async def index():
    """返回前端单页界面。"""
    index_file = _STATIC_DIR / "index.html"
    if index_file.is_file():
        return FileResponse(index_file)
    return JSONResponse({"message": "Frontend not built. Check static/index.html"})


@app.get("/health", include_in_schema=False)
async def health():
    return {"status": "ok"}
