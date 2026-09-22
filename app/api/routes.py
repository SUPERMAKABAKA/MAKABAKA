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
import logging
from typing import Any, Optional

from fastapi import APIRouter, Header, Request
from fastapi.responses import JSONResponse, StreamingResponse

from app.api.auth import resolve_user
from app.api.models import (
    ChatRequest,
    ChatResponse,
    ConsultationRequest,
    ConsultationResponse,
    ConsultationSummaryResponse,
    ErrorResponse,
)
from app.agents.consultation_summary import ConsultationSummary
from app.agents.customer_service import CustomerService
from app.config import get_settings
from app.container import Container
from app.orchestrator.graph import build_default_orchestrator
from app.orchestrator.session import ChatTurn, ConversationSession
from app.repositories.product_catalog import ProductCatalog
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
        self.catalog = ProductCatalog(settings.products_dataset)

        # 服务首次启动时自动恢复最初的本地推荐模式：空库就灌入预置商品，
        # 不再要求用户额外手动运行 scripts.ingest。
        if store.count() == 0:
            try:
                from app.rag.ingestion import IngestionPipeline

                written = IngestionPipeline(
                    crawler=container.crawler(),
                    store=store,
                    embedder=embedder,
                    logger=logging.getLogger("app.ingest"),
                ).run()
                logging.getLogger("app.ingest").info(
                    "启动时自动灌库完成，写入记录数=%d", written
                )
            except Exception:  # noqa: BLE001 - 保留 API 启动，错误在日志中可见
                logging.getLogger("app.ingest").exception("启动时自动灌库失败")

        orchestrator, _bundle = build_default_orchestrator(
            container, store, embedder, profile_source, catalog=self.catalog
        )
        self.orchestrator = orchestrator
        self.llm = container.llm()
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
        intent=result.intent,
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
    # 生成答案方式：direct=Nova自主决策多 / guided=human-in-the-loop多。
    if req.pace in ("direct", "guided"):
        session.pace = req.pace
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


@router.post(
    "/consult",
    response_model=ConsultationResponse,
    responses={400: {"model": ErrorResponse}, 409: {"model": ErrorResponse}},
)
@router.post(
    "/chat/consult",
    response_model=ConsultationResponse,
    include_in_schema=False,
)
async def consult(request: ConsultationRequest) -> Any:
    """基于当前会话推荐商品生成模拟人工客服答复。"""
    components = _get_components()
    session = components.session_repo.get_or_create(request.session_id)
    recommendations = list(session.recommendations)
    if not recommendations:
        return JSONResponse(
            status_code=409,
            content=ErrorResponse(
                error="当前会话还没有可咨询的推荐商品，请先获取推荐。"
            ).model_dump(),
        )

    if request.product_ids:
        selected_ids = set(request.product_ids)
        selected = [item for item in recommendations if item.product_id in selected_ids]
        if not selected:
            return JSONResponse(
                status_code=400,
                content=ErrorResponse(error="未找到请求咨询的推荐商品。").model_dump(),
            )
        recommendations = selected

    reply = CustomerService.answer(request.message, recommendations)
    return ConsultationResponse(
        session_id=request.session_id,
        reply=reply,
        recommendations=recommendations,
    )


@router.post(
    "/consult/summary",
    response_model=ConsultationSummaryResponse,
    responses={400: {"model": ErrorResponse}, 409: {"model": ErrorResponse}},
)
async def consult_summary(request: ConsultationRequest) -> Any:
    """基于当前会话推荐商品生成客服咨询，并把咨询内容总结后回复。"""
    components = _get_components()
    session = components.session_repo.get_or_create(request.session_id)
    recommendations = list(session.recommendations)
    if not recommendations:
        return JSONResponse(
            status_code=409,
            content=ErrorResponse(
                error="当前会话还没有可咨询的推荐商品，请先获取推荐。"
            ).model_dump(),
        )

    if request.product_ids:
        selected_ids = set(request.product_ids)
        selected = [item for item in recommendations if item.product_id in selected_ids]
        if not selected:
            return JSONResponse(
                status_code=400,
                content=ErrorResponse(error="未找到请求咨询的推荐商品。").model_dump(),
            )
        recommendations = selected

    transcript = CustomerService.answer(request.message, recommendations)
    summary = ConsultationSummary(components.llm).summarize(transcript, recommendations)
    return ConsultationSummaryResponse(
        session_id=request.session_id,
        reply=summary,
        summary=summary,
        transcript=transcript,
        recommendations=recommendations,
    )


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
            "intent": result.intent,
            "consult_offer": bool(recs),
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
