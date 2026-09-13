"""共享状态对象 ConversationSession 及其子模型 (Req 8.2)。

ConversationSession 是在所有 Agent 间传递的唯一状态载体。LangGraph 以其为
图状态类型；每个 Agent 只追加/更新自己负责的字段，从而实现状态的单调累积。

本模块只实现任务 2.1 的核心状态模型。`UserProfile` 与 `ProductRecommendation`
由任务 2.2 提供，此处以前向引用声明，运行时通过 model_rebuild 惰性解析，二者
默认值分别为 ``None`` 与空列表，故本模块可独立导入与实例化。
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Literal, Optional

from pydantic import BaseModel, Field

if TYPE_CHECKING:  # 仅用于类型检查，避免与任务 2.2 产生运行时循环依赖
    from app.orchestrator.session import ProductRecommendation, UserProfile


class CollectedNeeds(BaseModel):
    budget: Optional[float] = None
    purpose: Optional[str] = None
    preferences: Optional[list[str]] = None
    confirmed_features: dict[str, bool] = Field(default_factory=dict)  # yes/no 确认结果


class ReactStep(BaseModel):
    """ReAct 展示步骤：向前端呈现「思考-计划-行动」链路（展示层，非 LLM 推理循环）。"""

    thought: str
    plan: str
    action: str




class RetrievedRecord(BaseModel):
    product_id: str
    source_url: str
    matched_text: str          # 匹配到的评论/详情文本 (Req 5.2)
    relevance_score: float


class SocialReview(BaseModel):
    platform: Literal["xiaohongshu", "douyin", "bilibili"]
    sentiment: Literal["positive", "negative"]
    content: str


class WebInfo(BaseModel):
    product_id: str
    product_info: str
    social_reviews: list[SocialReview] = Field(default_factory=list)


class ChatTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class AgentError(BaseModel):
    agent: str        # 失败 Agent 标识 (Req 8.4)
    message: str


class ConversationSession(BaseModel):
    # 标识
    session_id: str
    user_id: Optional[str] = None

    # 流程控制
    stage: Literal["profile", "clarify", "retrieval",
                   "web_search", "recommendation", "done", "error"] = "profile"
    pace: Literal["direct", "guided"] = "guided"
    cold_start: bool = False               # Req 3.2
    category: Optional[str] = None         # 当前会话识别出的商品品类（换品类视为新需求）
    error: Optional[AgentError] = None     # Req 8.4

    # Profile / 需求
    user_profile: Optional["UserProfile"] = None
    collected_needs: CollectedNeeds = Field(default_factory=CollectedNeeds)

    # 对话
    messages: list[ChatTurn] = Field(default_factory=list)
    pending_question: Optional[str] = None  # clarify 让出时产出的问题
    clarify_options: list[str] = Field(default_factory=list)  # 当前澄清问题的可选项（供前端按钮选择）
    react_steps: list[ReactStep] = Field(default_factory=list)  # ReAct 展示步骤（思考-计划-行动）

    # Agent 中间结果
    retrieval_results: list[RetrievedRecord] = Field(default_factory=list)
    retrieval_status: Literal["ok", "no_match"] = "ok"       # Req 5.3
    web_results: list[WebInfo] = Field(default_factory=list)
    web_status: Literal["ok", "no_review"] = "ok"            # Req 6.4

    # 输出
    recommendation_count: Optional[int] = None               # Req 9.5
    recommendations: list["ProductRecommendation"] = Field(default_factory=list)
    recommendation_status: Literal["ok", "insufficient"] = "ok"  # Req 7.6

    updated_at: datetime = Field(default_factory=datetime.utcnow)

    def needs_complete(self) -> bool:
        """封装 Direct/Guided 的需求就绪差异 (Req 4.4 / 4.5)。

        - Direct：收集到预算 + 用途即可推进。
        - Guided：预算、用途、偏好三项都需就绪。
        """
        collected = self.collected_needs
        if self.pace == "direct":
            return collected.budget is not None and collected.purpose is not None
        # guided：预算、用途、偏好三项都需就绪
        return (collected.budget is not None
                and collected.purpose is not None
                and collected.preferences is not None)


# `UserProfile` 与 `ProductRecommendation` 由任务 2.2 补充。为使本模块可独立导入与
# 实例化，先尝试解析真实模型；若尚未定义，则用宽松占位类型完成前向引用解析（这些
# 字段默认值分别为 None 与空列表，占位不影响本任务功能）。任务 2.2 定义真实模型后
# 会再次调用 model_rebuild 完成精确解析。
try:  # pragma: no cover - 依任务 2.2 是否就绪走不同分支
    from app.orchestrator.models import (  # type: ignore  # noqa: F401
        ProductRecommendation,
        UserProfile,
    )

    ConversationSession.model_rebuild()
except Exception:  # noqa: BLE001 - 占位解析，保证 2.1 独立可用
    from typing import Any as _Any

    ConversationSession.model_rebuild(
        _types_namespace={"UserProfile": _Any, "ProductRecommendation": _Any}
    )
