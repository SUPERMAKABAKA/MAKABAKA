"""FastAPI 应用入口。

装配 Container、会话仓与 Orchestrator（在 ``app.api.routes`` 内一次性完成），
挂载 ``/chat`` 对话路由，并托管前端单页界面（``static/index.html``）。
"""

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes import router as chat_router

app = FastAPI(title="RAG 多 Agent 购物助手")

# 挂载 /chat 对话路由（Req 9.1~9.5, 8.4）
app.include_router(chat_router)

_STATIC_DIR = Path(__file__).parent / "static"

# 托管静态资源（若有额外的 css/js/图片可放入 static/assets）
if (_STATIC_DIR / "assets").is_dir():
    app.mount("/assets", StaticFiles(directory=_STATIC_DIR / "assets"), name="assets")


@app.get("/", include_in_schema=False)
async def index():
    """返回前端单页界面。"""
    index_file = _STATIC_DIR / "index.html"
    if index_file.is_file():
        return FileResponse(index_file)
    return JSONResponse({"message": "前端未构建，请检查 static/index.html"})


@app.get("/health", include_in_schema=False)
async def health():
    """健康检查。"""
    return {"status": "ok"}
