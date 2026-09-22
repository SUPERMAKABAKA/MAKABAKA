"""输出与画像数据模型。

按 design.md "Data Models" 章节定义 `ReviewSummary`、`ProductRecommendation`
与 `UserProfile`。关联需求：3.4、7.4、7.5。

为避免与任务 2.1（`app/orchestrator/session.py`）的编辑冲突，这三个模型放置于
本独立文件中，供 Recommendation_Agent、Profile_Agent 与会话状态复用。
"""

from typing import Optional

from pydantic import BaseModel, Field


class ReviewSummary(BaseModel):
    """基于评论与社媒测评聚合的好评/差评总结 (Req 7.5)。"""

    positives: list[str] = Field(default_factory=list)  # 好评要点 (Req 7.5)
    negatives: list[str] = Field(default_factory=list)  # 差评要点 (Req 7.5)


class ProductRecommendation(BaseModel):
    """单条商品推荐输出模型 (Req 7.4, 7.5)。"""

    product_id: str
    title: str
    reason: str  # 推荐理由 (Req 7.4)
    product_url: str  # 商品链接 (Req 7.4)
    summary: ReviewSummary  # 基于评论+测评的好评/差评总结 (Req 7.4, 7.5)
    detail: str = ""  # 商品详情，供前端和模拟客服引用
    price: Optional[str | float] = None
    rating: Optional[float] = None
    review_count: int = 0
    relevance_score: Optional[float] = None


class UserProfile(BaseModel):
    """模拟用户画像 (Req 3.4)。"""

    user_id: str
    preferences: list[str]
    budget: Optional[float] = None
    purpose: Optional[str] = None
