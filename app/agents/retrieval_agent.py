"""Retrieval_Agent：基于 RAG 的 Chroma 相似度检索 (Req 5.1-5.4, 8.2)。

按 design.md 的 "RAG Retrieval Design（检索设计）" 章节契约，Retrieval_Agent
将 ``session.collected_needs`` 组织为查询文本，向量化后在 Chroma 中做相似度
检索：

- 由预算 / 用途 / 偏好拼装查询文本，经 embedder 向量化后调用
  ``store.query(top_k=20)`` 检索候选（Req 5.1）。
- 将每条命中映射为 ``RetrievedRecord``，携带 product_id、source_url 与匹配
  文本（Req 5.2），相关度取 ``1 / (1 + distance)``。
- 结果按相关度降序排序（Req 5.4），写入 ``session.retrieval_results``。
- 命中则 ``retrieval_status="ok"``，无匹配则返回空列表并置 ``"no_match"``，
  流程继续（Req 5.3）。
- 捕获到不可恢复错误 → 设置 ``session.error = AgentError(agent="retrieval",
  ...)`` 供 Orchestrator 据此终止（Req 8.4）。

Retrieval_Agent 仅经注入的向量库与 embedder 访问外部依赖，符合“外部依赖只经
接口访问”的约束。
"""

from __future__ import annotations

from typing import Optional

from app.agents.category import category_query_terms, detect_category
from app.orchestrator.session import (
    AgentError,
    CollectedNeeds,
    ConversationSession,
    RetrievedRecord,
)
from app.rag.vector_store import VectorStore

__all__ = ["RetrievalAgent"]


class RetrievalAgent:
    """将需求组织为查询并在 Chroma 中做相似度检索 (Req 5.1-5.4)。"""

    name = "retrieval"

    def __init__(self, store: VectorStore, embedder) -> None:
        """初始化 Retrieval_Agent。

        Args:
            store: 向量库封装，提供 ``query(embedding, top_k)`` 契约。
            embedder: 可调用的文本向量化器，契约为 ``embedder(text) -> list``。
        """
        self._store = store
        self._embed = embedder

    def run(self, session: ConversationSession) -> ConversationSession:
        """执行 RAG 检索并更新会话状态 (Req 5.1-5.4, 8.2)。

        Args:
            session: 共享会话状态，读取 ``collected_needs``。

        Returns:
            更新后的 ``ConversationSession``：写入按相关度降序的
            ``retrieval_results`` 与 ``retrieval_status``；异常时置 ``error``。
        """
        try:
            # 品类兜底识别：不同对话路径（LLM / clarify fallback）可能未写入
            # session.category，这里从需求用途与历史用户消息中补识别，保证品类
            # 过滤在检索/推荐阶段可靠生效。
            if not session.category:
                session.category = self._infer_category(session)

            query = self._build_query(session.collected_needs, session.category)
            # 返回含 metadata + distance 的命中列表 (Req 5.1)
            hits = self._store.query(self._embed(query), top_k=20)
            results = [
                RetrievedRecord(
                    product_id=h.metadata["product_id"],
                    source_url=h.metadata["source_url"],  # Req 5.2
                    matched_text=h.metadata["original_text"],
                    relevance_score=1.0 / (1.0 + h.distance),
                    detail=str(h.metadata.get("detail") or "") or None,
                )
                for h in hits
            ]
        except Exception as exc:  # noqa: BLE001 - 不可恢复错误统一传播 (Req 8.4)
            session.error = AgentError(
                agent=self.name,
                message=f"检索失败：{exc}",
            )
            return session

        # 按相关度降序排序 (Req 5.4)
        results.sort(key=lambda r: r.relevance_score, reverse=True)

        # 品类重排：确定性哈希 embedding 语义弱，容易检索跑偏（如问“耳机”返回
        # 厨具）。若已识别品类，则把商品文本/详情含该品类关键词的记录优先排到
        # 前面，保证推荐商品与用户品类一致。命中品类的记录整体前置，其余按原
        # 相关度顺序保留在后（兜底，避免品类无命中时结果为空）。
        terms = category_query_terms(session.category)
        if terms:
            lowered_terms = [t.lower() for t in terms]

            def _is_category_match(record: RetrievedRecord) -> bool:
                text = ((record.detail or "") + " " + (record.matched_text or "")).lower()
                return any(term in text for term in lowered_terms)

            matched = [r for r in results if _is_category_match(r)]
            others = [r for r in results if not _is_category_match(r)]
            if matched:
                results = matched + others

        session.retrieval_results = results
        # 命中即 ok，空结果置 no_match，流程继续 (Req 5.3)
        session.retrieval_status = "ok" if results else "no_match"
        return session

    @staticmethod
    def _infer_category(session: ConversationSession) -> Optional[str]:
        """从需求用途与历史用户消息中识别品类（兜底，返回规范品类名或 None）。"""
        candidates: list[str] = []
        if session.collected_needs.purpose:
            candidates.append(session.collected_needs.purpose)
        for turn in session.messages:
            if turn.role == "user" and turn.content:
                candidates.append(turn.content)
        for text in candidates:
            found = detect_category(text)
            if found:
                return found
        return None

    @staticmethod
    def _build_query(collected_needs: CollectedNeeds, category: Optional[str] = None) -> str:
        """由收集到的需求拼装检索查询文本。

        将预算、用途、偏好等已收集字段组织为一段自然语言查询，供 embedder
        向量化。缺失字段跳过，保证查询稳定可复现。

        Args:
            collected_needs: 当前已收集的需求。

        Returns:
            拼接后的查询文本；无任何需求时返回空串。
        """
        parts: list[str] = []
        # 品类是最强的语义锚点，优先纳入查询，避免检索跑偏到不相关品类。
        terms = category_query_terms(category)
        if terms:
            parts.append("品类：" + " ".join(terms))
        elif category:
            parts.append(f"品类：{category}")
        if collected_needs.purpose:
            parts.append(f"用途：{collected_needs.purpose}")
        if collected_needs.budget is not None:
            parts.append(f"预算：{collected_needs.budget}")
        if collected_needs.preferences:
            parts.append("偏好：" + "、".join(collected_needs.preferences))
        return " ".join(parts)
