"""FastAPI 应用入口（任务 16.2）。

装配 Container、会话仓与 Orchestrator（在 ``app.api.routes`` 内一次性完成），
并将 ``/chat`` 对话路由挂载到应用。保留根路由作为健康检查。
"""

from fastapi import FastAPI

from app.api.routes import router as chat_router

app = FastAPI(title="RAG 多 Agent 购物助手")

# 挂载 /chat 对话路由（Req 9.1~9.5, 8.4）
app.include_router(chat_router)


@app.get("/")
async def root():
    """健康检查根路由。"""
    return {"message": "Hello World"}
