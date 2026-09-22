"""对话接口的请求/响应数据模型。

按 design.md "API Design" 章节定义 `ChatRequest`、`ChatResponse` 与
`ErrorResponse`。关联需求：9.1、9.4、9.5。
"""

from typing import Literal, Optional

from pydantic import BaseModel, Field

from app.orchestrator.models import ProductRecommendation


class ChatRequest(BaseModel):
    """/chat 请求模型 (Req 9.1)。"""

    session_id: str
    message: str
    recommendation_count: Optional[int] = Field(default=None, ge=1)  # Req 9.5
    pace: Optional[str] = Field(default=None, description="direct = Nova自主决策多; guided = human-in-the-loop多")


class ChatResponse(BaseModel):
    """/chat 响应模型 (Req 9.1)。"""

    session_id: str
    stage: str
    assistant_message: Optional[str] = None  # 澄清问题或提示
    recommendations: list[ProductRecommendation] = Field(default_factory=list)  # 推荐完成时返回
    recommendation_status: Optional[str] = None  # ok / insufficient
    notices: list[str] = Field(default_factory=list)  # no_match / no_review 等提示
    options: list[str] = Field(default_factory=list)  # 澄清问题的可选项（前端按钮）
    react_steps: list[dict] = Field(default_factory=list)  # ReAct 展示步骤
    intent: str = "chat"  # chat / recommend


class ConsultationRequest(BaseModel):
    """基于当前会话推荐商品发起模拟客服咨询。"""

    session_id: str
    message: str = "请像人工客服一样介绍这些推荐商品，并说明各自优缺点。"
    product_ids: list[str] = Field(default_factory=list)


class ConsultationResponse(BaseModel):
    """模拟客服的可解释回复及其引用的推荐商品。"""

    session_id: str
    reply: str
    recommendations: list[ProductRecommendation] = Field(default_factory=list)


class ConsultationSummaryResponse(ConsultationResponse):
    """在客服回复基础上叠加总结：``reply`` 仍为面向用户的总结。"""

    summary: str  # Consultation_Summary（= reply）
    transcript: str  # 原始客服文案（Consultation_Transcript）


class ErrorResponse(BaseModel):
    """错误响应模型 (Req 9.4)。"""

    error: str
    missing_fields: list[str] = Field(default_factory=list)  # Req 9.4
    failed_agent: Optional[str] = None  # Req 8.4
