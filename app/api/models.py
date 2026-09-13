"""对话接口的请求/响应数据模型。

按 design.md "API Design" 章节定义 `ChatRequest`、`ChatResponse` 与
`ErrorResponse`。关联需求：9.1、9.4、9.5。
"""

from typing import Optional

from pydantic import BaseModel, Field

from app.orchestrator.models import ProductRecommendation


class ChatRequest(BaseModel):
    """/chat 请求模型 (Req 9.1)。"""

    session_id: str
    message: str
    recommendation_count: Optional[int] = Field(default=None, ge=1)  # Req 9.5


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


class ErrorResponse(BaseModel):
    """错误响应模型 (Req 9.4)。"""

    error: str
    missing_fields: list[str] = Field(default_factory=list)  # Req 9.4
    failed_agent: Optional[str] = None  # Req 8.4
