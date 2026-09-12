"""对话接口 /chat 路由（任务 16.2）。

按 design.md "API Design" 章节实现 ``POST /chat``：

- 缺 ``session_id`` / ``message`` → 400，``missing_fields`` 列出缺失字段名
  （Req 9.4）。
- 按 ``session_id`` 定位会话并驱动 Orchestrator（Req 9.2）。
- 透传 ``recommendation_count`` 给 Recommendation_Agent（Req 9.5）。
- Agent 错误 → 500，``failed_agent`` 标识失败 Agent（Req 8.4）。
- 推荐完成时响应含推荐列表与 notices（Req 9.3）。

装配说明：模块级一次性装配 Container、RAG 组件、Orchestrator 与会话仓，
供路由复用同一编排图与会话状态。LangGraph 编译图 ``invoke`` 返回的是 dict，
需用 ``ConversationSession.model_validate`` 转回模型再读字段。
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.api.models import ChatRequest, ChatResponse, ErrorResponse
from app.config import get_settings
from app.container import Container
from app.orchestrator.graph import build_default_orchestrator
from app.orchestrator.session import ChatTurn, ConversationSession
from app.rag.embedder import DeterministicEmbedder
from app.rag.vector_store import VectorStore
from app.repositories.profile_source import MockProfileSource
from app.repositories.session_repo import InMemorySessionRepository

__all__ = ["router", "build_components"]


class _Components:
    """一次性装配的运行期组件集合。

    持有编排图与会话仓，供 ``/chat`` 路由复用。集中装配确保多轮请求共享
    同一 Orchestrator 与会话状态（Req 9.2）。
    """

    def __init__(self) -> None:
        settings = get_settings()
        container = Container(settings)
        store = VectorStore(chroma_dir=settings.chroma_dir)
        embedder = DeterministicEmbedder()
        profile_source = MockProfileSource(settings.profiles_dataset)
        orchestrator, _bundle = build_default_orchestrator(
            container, store, embedder, profile_source
        )
        self.orchestrator = orchestrator
        self.session_repo = InMemorySessionRepository()


def build_components() -> _Components:
    """装配并返回运行期组件（Container / Orchestrator / 会话仓）。"""
    return _Components()


# 模块级单例：应用启动即装配一次，路由复用。
_components: _Components | None = None


def _get_components() -> _Components:
    """惰性获取模块级组件单例，避免在导入期就构建向量库客户端。"""
    global _components
    if _components is None:
        _components = build_components()
    return _components


router = APIRouter()


def _to_chat_response(result: ConversationSession) -> ChatResponse:
    """将编排后的会话状态映射为 ``ChatResponse``（Req 9.3）。

    - 澄清阶段（有 ``pending_question``）时把问题作为 ``assistant_message``。
    - 汇总 ``retrieval_status`` / ``web_status`` 的空结果提示为 ``notices``。
    """
    notices: list[str] = []
    if result.retrieval_status == "no_match":
        notices.append("未检索到匹配的商品，已基于可用信息给出建议。")
    if result.web_status == "no_review":
        notices.append("未找到相关社媒测评，推荐仅基于商品信息与评论。")

    return ChatResponse(
        session_id=result.session_id,
        stage=result.stage,
        assistant_message=result.pending_question,
        recommendations=result.recommendations,
        recommendation_status=result.recommendation_status,
        notices=notices,
    )


@router.post(
    "/chat",
    response_model=ChatResponse,
    responses={400: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
)
async def chat(request: Request) -> Any:
    """对话接口：驱动多 Agent 编排并返回澄清问题或推荐结果。

    直接解析原始请求体以便对缺字段返回明确的 ``missing_fields``（Req 9.4），
    而非 FastAPI 默认的 422 校验错误。
    """
    try:
        body = await request.json()
    except Exception:
        body = None
    if not isinstance(body, dict):
        body = {}

    # 缺字段校验：session_id / message 为空或缺失均记入 missing_fields（Req 9.4）
    missing = [
        field
        for field in ("session_id", "message")
        if not body.get(field)
    ]
    if missing:
        return JSONResponse(
            status_code=400,
            content=ErrorResponse(
                error="missing required fields", missing_fields=missing
            ).model_dump(),
        )

    req = ChatRequest.model_validate(body)

    components = _get_components()
    session = components.session_repo.get_or_create(req.session_id)  # Req 9.2
    session.recommendation_count = req.recommendation_count          # Req 9.5
    session.messages.append(ChatTurn(role="user", content=req.message))

    # LangGraph 编译图 invoke 返回 dict，需转回 ConversationSession 再读字段。
    result_dict = components.orchestrator.invoke(session)
    result = ConversationSession.model_validate(result_dict)

    if result.error:  # Req 8.4
        return JSONResponse(
            status_code=500,
            content=ErrorResponse(
                error=result.error.message, failed_agent=result.error.agent
            ).model_dump(),
        )

    components.session_repo.save(result)
    return _to_chat_response(result)  # Req 9.3
