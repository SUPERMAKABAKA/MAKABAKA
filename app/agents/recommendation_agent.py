"""Recommendation_Agent：综合生成商品推荐 (Req 7.1–7.6, 8.2)。

按 design.md "5 个 Agent" 表格的 Recommendation_Agent 行，本 Agent 融合
``retrieval_results`` 与 ``web_results``，为每个候选商品生成一条
``ProductRecommendation``：

- ``reason``：结合已收集需求 (``collected_needs``) 与检索匹配文本生成推荐理由
  （Req 7.4，非空）。
- ``product_url``：取自对应检索记录的 ``source_url``（Req 7.4）。
- ``summary``：``ReviewSummary``，从该商品的社媒测评 (``social_reviews``) 中按
  情感聚合好评/差评两方面内容（Req 7.5）。

数量策略：
- 用户显式指定数量时按数量输出（Req 7.3）。
- 未指定时默认落在 3–5 条区间（Req 7.2）。
- 候选不足目标数量时返回全部候选并置 ``recommendation_status="insufficient"``
  （Req 7.6）。

外部依赖只经接口访问：本 Agent 通过 ``LLM_Interface`` 生成推荐理由；未注入
LLM 时退化为确定性模板，保证离线可用。
"""

from __future__ import annotations

import json
import re
from typing import Optional

from app.interfaces.llm import LLMInterface
from app.orchestrator.models import ProductRecommendation, ReviewSummary
from app.orchestrator.session import (
    AgentError,
    ConversationSession,
    RetrievedRecord,
    WebInfo,
)

__all__ = ["RecommendationAgent"]

# 未指定数量时的默认推荐区间下/上限 (Req 7.2)
_DEFAULT_MIN = 3
_DEFAULT_MAX = 5


class RecommendationAgent:
    """融合检索与联网结果生成推荐列表 (Req 7.1–7.6)。"""

    name = "recommendation"

    def __init__(self, llm: Optional[LLMInterface] = None) -> None:
        """初始化 Recommendation_Agent。

        Args:
            llm: LLM 接口实现，用于生成推荐理由；仅依赖抽象类型便于替换
                （Req 2.1, 2.4）。为 ``None`` 时使用确定性模板生成理由。
        """
        self._llm = llm

    def run(self, session: ConversationSession) -> ConversationSession:
        """生成推荐列表并更新会话状态 (Req 7.1–7.6, 8.2)。

        Args:
            session: 共享会话状态，读取 ``retrieval_results``、``web_results``
                与 ``recommendation_count``。

        Returns:
            更新后的 ``ConversationSession``：写入 ``recommendations`` 与
            ``recommendation_status``；候选不足目标数量时置 ``"insufficient"``
            （Req 7.6）；异常时置 ``error``（Req 8.4）。
        """
        try:
            # 按 product_id 去重得到候选，保持相关度顺序 (Req 7.1)
            candidates = self._dedupe_candidates(session.retrieval_results)
            web_index = self._index_web_results(session.web_results)

            # 计算目标数量 (Req 7.2, 7.3)
            target = self._resolve_target(session.recommendation_count, len(candidates))

            # 候选不足目标数量：返回全部并标记 insufficient (Req 7.6)
            if len(candidates) < target:
                selected = candidates
                session.recommendation_status = "insufficient"
            else:
                selected = candidates[:target]
                session.recommendation_status = "ok"

            # 一次性批量生成全部推荐理由，避免逐条调用 LLM 触发限流/超时；
            # 批量失败或条数不匹配时，逐条回退（_build_reason 内含模板兜底）。
            batch_reasons = self._batch_reasons(selected, web_index, session)
            recommendations = [
                self._build_recommendation(
                    record,
                    web_index.get(record.product_id),
                    session,
                    reason=batch_reasons[i] if batch_reasons else None,
                )
                for i, record in enumerate(selected)
            ]
            session.recommendations = recommendations
        except Exception as exc:  # noqa: BLE001 - 不可恢复错误统一传播 (Req 8.4)
            session.error = AgentError(
                agent=self.name,
                message=f"生成推荐失败：{exc}",
            )
        return session

    @staticmethod
    def _dedupe_candidates(
        retrieval_results: list[RetrievedRecord],
    ) -> list[RetrievedRecord]:
        """按 ``product_id`` 去重，保留首次出现（即相关度更高）的记录。"""
        seen: set[str] = set()
        candidates: list[RetrievedRecord] = []
        for record in retrieval_results:
            if record.product_id in seen:
                continue
            seen.add(record.product_id)
            candidates.append(record)
        return candidates

    @staticmethod
    def _index_web_results(web_results: list[WebInfo]) -> dict[str, WebInfo]:
        """按 ``product_id`` 建立联网结果索引，便于与候选匹配。"""
        return {info.product_id: info for info in web_results}

    @staticmethod
    def _resolve_target(count: Optional[int], candidate_count: int) -> int:
        """计算目标推荐数量 (Req 7.2, 7.3)。

        - 用户指定数量：直接采用（Req 7.3）。
        - 未指定：默认落在 3–5 之间，且不超过候选数（Req 7.2）；候选充足时
          倾向输出上限 5，候选不足下限 3 时目标即为其自身（触发 insufficient）。
        """
        if count is not None:
            return count
        # 默认目标：至少 3，至多 5，且不超过候选数
        return max(_DEFAULT_MIN, min(_DEFAULT_MAX, candidate_count))

    def _build_recommendation(
        self,
        record: RetrievedRecord,
        web_info: Optional[WebInfo],
        session: ConversationSession,
        reason: Optional[str] = None,
    ) -> ProductRecommendation:
        """基于检索记录与对应联网结果构造单条推荐 (Req 7.4, 7.5)。

        ``reason`` 为批量生成的预填理由；为空时逐条回退到 ``_build_reason``。
        """
        title = self._resolve_title(record, web_info)
        cleaned = self._clean_llm(reason) if reason else ""
        reason = cleaned or self._build_reason(record, web_info, session)
        summary = self._build_summary(web_info)
        return ProductRecommendation(
            product_id=record.product_id,
            title=title,
            reason=reason,
            product_url=record.source_url,  # Req 7.4
            summary=summary,
        )

    @staticmethod
    def _resolve_title(record: RetrievedRecord, web_info: Optional[WebInfo]) -> str:
        """确定商品标题：优先联网商品信息首行，否则回退到 product_id。"""
        if web_info is not None and web_info.product_info:
            first_line = web_info.product_info.strip().splitlines()[0].strip()
            if first_line:
                return first_line
        return record.product_id

    def _batch_reasons(
        self,
        records: list,
        web_index: dict,
        session: ConversationSession,
    ) -> Optional[list]:
        """一次 LLM 调用为所有商品生成推荐理由，返回与 ``records`` 等长的列表。

        将全部候选商品打包进单个 prompt，要求模型返回 JSON 字符串数组，从而把
        请求数从 N 次降到 1 次，规避免费额度的每分钟限流 (RPM)。

        返回：
          * 成功且条数匹配 → ``list[str]``（逐条已过 ``_clean_llm``）。
          * 无 LLM / 调用失败 / 解析失败 / 条数不匹配 → ``None``（由上层逐条回退）。
        """
        if self._llm is None or not records:
            return None

        needs = self._describe_needs(session)
        lines = []
        for i, record in enumerate(records):
            web_info = web_index.get(record.product_id)
            product_info = web_info.product_info if web_info is not None else ""
            lines.append(
                f"{i}. product_id={record.product_id} | "
                f"matched={record.matched_text} | info={product_info}"
            )
        catalog = "\n".join(lines)
        prompt = (
            "You are a shopping assistant. For EACH product below, write one "
            "concise English sentence explaining why it fits the shopper. "
            "Return ONLY a JSON array of strings, one per product, in the same "
            "order, with no markdown, no code fences, no extra text.\n"
            f"Shopper needs: {needs}\n"
            f"Products:\n{catalog}"
        )

        try:
            generated = self._llm.generate(prompt)
        except Exception:  # noqa: BLE001 - 批量调用失败时回退逐条
            return None

        reasons = self._parse_reason_array(generated, len(records))
        return reasons

    @staticmethod
    def _parse_reason_array(text: Optional[str], expected: int) -> Optional[list]:
        """从 LLM 输出中解析 JSON 字符串数组，条数需与 ``expected`` 一致。

        容忍模型偶尔包裹的 ```` ```json ```` 代码围栏；解析失败或条数不符返回
        ``None``。
        """
        if not text:
            return None
        cleaned = text.strip()
        # 去除可能的 markdown 代码围栏
        fence = re.match(r"^```[a-zA-Z]*\s*(.*?)\s*```$", cleaned, re.DOTALL)
        if fence:
            cleaned = fence.group(1).strip()
        # 截取首个 [ 到末个 ] 之间的内容，容忍前后杂散文本
        start = cleaned.find("[")
        end = cleaned.rfind("]")
        if start == -1 or end == -1 or end <= start:
            return None
        try:
            arr = json.loads(cleaned[start : end + 1])
        except (ValueError, TypeError):
            return None
        if not isinstance(arr, list) or len(arr) != expected:
            return None
        return [str(x) for x in arr]

    def _build_reason(
        self,
        record: RetrievedRecord,
        web_info: Optional[WebInfo],
        session: ConversationSession,
    ) -> str:
        """生成非空推荐理由 (Req 7.4)。

        结合已收集需求与检索匹配文本构造提示词；若注入了 LLM 则由其生成，
        否则回退到确定性模板，确保结果始终非空。
        """
        needs = self._describe_needs(session)
        product_info = web_info.product_info if web_info is not None else ""
        prompt = (
            "In one concise English sentence, explain why this product fits "
            "the shopper. Do not repeat the prompt.\n"
            f"Shopper needs: {needs}\n"
            f"Product: {record.product_id}\n"
            f"Matched review/detail: {record.matched_text}\n"
            f"Product info: {product_info}"
        )

        # LLM 生成理由，异常/超时时回退；输出经 _clean_llm 清洗防止回显泄漏
        if self._llm is not None:
            try:
                generated = self._llm.generate(prompt)
            except Exception:  # noqa: BLE001 - LLM 不可用/超时时回退到模板
                generated = None
            cleaned = self._clean_llm(generated)
            if cleaned:
                return cleaned

        # 无 LLM / LLM 返回被过滤：英文模板兜底，保证 reason 非空 (Req 7.4)
        base = record.matched_text.strip() or f"Product {record.product_id}"
        if needs:
            return f"Matches your needs ({needs}): {base} Worth a look."
        return f"{base} A solid fit for what you are after."

    @staticmethod
    def _clean_llm(text: Optional[str]) -> str:
        """清洗 LLM 输出，过滤空值与 MockLLM 回显，避免展示原始回显给用户。

        规则：
        - ``None`` 或空串 → ``""``。
        - ``strip`` 后为空 → ``""``。
        - 以 ``"[MockLLM]"`` 开头或包含 ``"response to:"`` → ``""``
          （这是 MockLLM 的回显，不能展示）。
        - 其余情况返回 ``strip`` 后的文本。
        """
        if not text:
            return ""
        stripped = text.strip()
        if not stripped:
            return ""
        if stripped.startswith("[MockLLM]") or "response to:" in stripped:
            return ""
        return stripped

    @staticmethod
    def _describe_needs(session: ConversationSession) -> str:
        """将 ``collected_needs`` 压缩为简短的英文需求描述片段。"""
        needs = session.collected_needs
        parts: list[str] = []
        if needs.budget is not None:
            parts.append(f"budget {needs.budget}")
        if needs.purpose:
            parts.append(f"use case {needs.purpose}")
        if needs.preferences:
            parts.append("prefers " + ", ".join(needs.preferences))
        return "; ".join(parts)

    @staticmethod
    def _build_summary(web_info: Optional[WebInfo]) -> ReviewSummary:
        """从社媒测评聚合好评/差评两方面内容 (Req 7.5)。"""
        positives: list[str] = []
        negatives: list[str] = []
        if web_info is not None:
            for review in web_info.social_reviews:
                if review.sentiment == "positive":
                    positives.append(review.content)
                elif review.sentiment == "negative":
                    negatives.append(review.content)
        return ReviewSummary(positives=positives, negatives=negatives)
