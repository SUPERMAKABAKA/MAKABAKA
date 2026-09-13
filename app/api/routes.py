"""对话接口 /chat 与 /chat/stream 路由。

- ``POST /chat``：一次性返回完整响应（Req 9.1~9.5, 8.4）。
- ``POST /chat/stream``：Server-Sent Events 流式返回助手文本与推荐结果，
  供前端做逐词流式呈现。

装配说明：模块级一次性装配 Container、RAG 组件、Orchestrator 与会话仓，
供路由复用。LangGraph 编译图 ``invoke`` 返回 dict，需用
``ConversationSession.model_validate`` 转回模型再读字段。
"""

from __future__ import annotations

import asyncio
import json
from typing import Any, Optional

from fastapi import APIRouter, Header, Request
from fastapi.responses import JSONResponse, StreamingResponse

from app.api.auth import resolve_user
from app.api.models import ChatRequest, ChatResponse, ErrorResponse
from app.config import get_settings
from app.container import Container
from app.orchestrator.graph import build_default_orchestrator
from app.orchestrator.session import ChatTurn, ConversationSession
from app.repositories.profile_source import MockProfileSource
from app.repositories.session_repo import InMemorySessionRepository

__all__ = ["router", "build_components"]


class _Components:
    """一次性装配的运行期组件集合（编排图 + 会话仓）。"""

    def __init__(self) -> None:
        settings = get_settings()
        container = Container(settings)
        store = container_store(container, settings)
        embedder = container.embedder()
        profile_source = MockProfileSource(settings.profiles_dataset)
        orchestrator, _bundle = build_default_orchestrator(
            container, store, embedder, profile_source
        )
        self.orchestrator = orchestrator
        self.session_repo = InMemorySessionRepository()


def container_store(container: Container, settings):
    """构造向量库封装（延迟导入避免循环依赖）。"""
    from app.rag.vector_store import VectorStore

    return VectorStore(chroma_dir=settings.chroma_dir)


def build_components() -> _Components:
    return _Components()


_components: Optional[_Components] = None


def _get_components() -> _Components:
    global _components
    if _components is None:
        _components = build_components()
    return _components


router = APIRouter()


def _notices_from(result: ConversationSession) -> list[str]:
    notices: list[str] = []
    if result.retrieval_status == "no_match":
        notices.append("No exact matches found. Suggestions are based on available data.")
    if result.web_status == "no_review":
        notices.append("No social reviews found. Recommendations rely on product info and reviews.")
    return notices


def _to_chat_response(result: ConversationSession) -> ChatResponse:
    return ChatResponse(
        session_id=result.session_id,
        stage=result.stage,
        assistant_message=result.pending_question,
        recommendations=result.recommendations,
        recommendation_status=result.recommendation_status,
        notices=_notices_from(result),
        options=list(result.clarify_options),
        react_steps=[step.model_dump() for step in result.react_steps],
    )


def _run_turn(body: dict, authorization: Optional[str]) -> Any:
    """执行一轮编排，返回 (result_session, error_response_or_None)。"""
    missing = [f for f in ("session_id", "message") if not body.get(f)]
    if missing:
        return None, JSONResponse(
            status_code=400,
            content=ErrorResponse(error="missing required fields", missing_fields=missing).model_dump(),
        )

    req = ChatRequest.model_validate(body)
    components = _get_components()
    session = components.session_repo.get_or_create(req.session_id)
    # 登录用户名作为模拟画像的 user_id（若已登录）。
    user = resolve_user(authorization)
    if user and not session.user_id:
        session.user_id = user
    session.recommendation_count = req.recommendation_count
    session.messages.append(ChatTurn(role="user", content=req.message))

    result_dict = components.orchestrator.invoke(session)
    result = ConversationSession.model_validate(result_dict)

    if result.error:
        return None, JSONResponse(
            status_code=500,
            content=ErrorResponse(error=result.error.message, failed_agent=result.error.agent).model_dump(),
        )

    components.session_repo.save(result)
    return result, None


@router.post(
    "/chat",
    response_model=ChatResponse,
    responses={400: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
)
async def chat(request: Request, authorization: Optional[str] = Header(default=None)) -> Any:
    """一次性对话接口。"""
    try:
        body = await request.json()
    except Exception:
        body = None
    if not isinstance(body, dict):
        body = {}
    result, err = _run_turn(body, authorization)
    if err is not None:
        return err
    return _to_chat_response(result)


@router.post("/chat/stream")
async def chat_stream(request: Request, authorization: Optional[str] = Header(default=None)):
    """SSE 流式对话接口。

    事件序列：
    - ``event: token``  data: {"text": "<片段>"}   逐词推送助手文本
    - ``event: recommendations`` data: {recommendations, status, notices}
    - ``event: done``   data: {}
    - ``event: error``  data: {error, ...}
    """
    try:
        body = await request.json()
    except Exception:
        body = None
    if not isinstance(body, dict):
        body = {}

    async def gen():
        result, err = _run_turn(body, authorization)
        if err is not None:
            payload = err.body.decode("utf-8") if hasattr(err, "body") else "{}"
            yield f"event: error\ndata: {payload}\n\n"
            return

        recs = result.recommendations
        if recs:
            text = result.pending_question or f"Based on your needs, here are {len(recs)} picks I vetted for you, from why they fit to what real buyers say:"
        else:
            text = result.pending_question or "I need a little more to give you a sharper recommendation."

        # 逐词流式推送（按空白与中文字符切分，兼顾中英）。
        for chunk in _tokenize(text):
            yield f"event: token\ndata: {json.dumps({'text': chunk})}\n\n"
            await asyncio.sleep(0.018)

        payload = {
            "recommendations": [r.model_dump() for r in recs],
            "status": result.recommendation_status,
            "notices": _notices_from(result),
            "stage": result.stage,
            "options": list(result.clarify_options),
            "react_steps": [step.model_dump() for step in result.react_steps],
        }
        yield f"event: recommendations\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"
        yield "event: done\ndata: {}\n\n"

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def _tokenize(text: str) -> list[str]:
    """把文本切成便于流式呈现的片段：英文按词（含尾随空格），中文按字。"""
    out: list[str] = []
    buf = ""
    for ch in text:
        if ch == " ":
            buf += ch
            out.append(buf)
            buf = ""
        elif "\u4e00" <= ch <= "\u9fff":
            if buf:
                out.append(buf)
                buf = ""
            out.append(ch)
        else:
            buf += ch
    if buf:
        out.append(buf)
    return out
