"""把模拟客服回复（Consultation_Transcript）提炼为面向用户的简明总结。

优先走 LLM 总结；LLM 不可用、调用失败或返回空白时回退到基于规则的总结。
规则回退仅使用 transcript 与 recommendation 已有字段，不臆造价格、星级或
其他事实性信息（Req 3.5）。

相关需求：3.1、3.2、3.4、3.5、5.2、5.3。
"""

from __future__ import annotations

from app.interfaces.llm import LLMInterface
from app.orchestrator.models import ProductRecommendation


class ConsultationSummary:
    """将客服咨询原文总结为一段简明中文回复。

    - 提供 ``llm`` 时：构造“仅基于给定客服内容做要点总结、不新增事实”的
      提示词调用 ``llm.generate``；任何异常或空白输出都回退规则总结。
    - 未提供 ``llm`` 或回退时：从 recommendation 的 ``reason`` 与
      ``summary.positives/negatives`` 组织 3~5 行要点，保证非空且不臆造数值。
    """

    def __init__(self, llm: LLMInterface | None = None) -> None:
        self.llm = llm

    def summarize(
        self,
        transcript: str,
        recommendations: list[ProductRecommendation],
    ) -> str:
        """把客服回复 ``transcript`` 提炼为面向用户的简明总结。

        Args:
            transcript: 一次客服咨询产生的原始客服回复内容。
            recommendations: 本次咨询涉及的推荐商品。

        Returns:
            一段简明中文总结；LLM 成功则用其输出，否则走规则回退。永不抛出。
        """
        if self.llm is not None:
            try:
                prompt = self._build_prompt(transcript, recommendations)
                result = self.llm.generate(prompt)
                if result and result.strip():
                    return result.strip()
            except Exception:  # noqa: BLE001 - 任意异常均回退规则，保证有输出
                pass
        return self._rule_summary(transcript, recommendations)

    @staticmethod
    def _build_prompt(
        transcript: str,
        recommendations: list[ProductRecommendation],
    ) -> str:
        """构造“仅基于客服内容做要点总结、不新增事实”的中文提示词。"""
        titles = ", ".join(
            (item.title or item.product_id) for item in recommendations
        )
        return (
            "You are a shopping assistant. Summarize the key points based ONLY on the "
            "customer-support content below. Do not add any price, star rating, or any "
            "fact not present in the original text. Write concise English covering the "
            "recommendation leaning, main pros, and things to note.\n"
            f"Products involved: {titles}\n"
            "Customer-support content:\n"
            f"{transcript}\n"
            "Provide the summary:"
        )

    @staticmethod
    def _rule_summary(
        transcript: str,
        recommendations: list[ProductRecommendation],
    ) -> str:
        """基于 recommendation 已有字段组织 3~5 行要点，不臆造价格/星级。"""
        if not recommendations:
            text = (transcript or "").strip()
            if text:
                return "Support summary:\n" + text
            return "No customer-support content to summarize yet. Please get recommendations and start a consultation first."

        lines: list[str] = ["Here is a summary of this customer-support consultation:"]
        for index, product in enumerate(recommendations, start=1):
            name = product.title or product.product_id
            reason = (product.reason or "").strip() or "Matches your current needs."
            positives = [p for p in product.summary.positives[:2] if p]
            negatives = [n for n in product.summary.negatives[:2] if n]
            parts = [f"{index}. {name}: recommendation leaning — {reason}"]
            if positives:
                parts.append("Main pros: " + "; ".join(positives))
            if negatives:
                parts.append("Things to note: " + "; ".join(negatives))
            lines.append(" ".join(parts))

        if len(recommendations) > 1:
            best = max(
                recommendations,
                key=lambda item: (
                    len(item.summary.positives),
                    -len(item.summary.negatives),
                ),
            )
            lines.append(
                f"Based on overall reputation, I'd suggest \"{best.title or best.product_id}\" first; "
                "please make the final decision together with the live info on the product page."
            )
        return "\n".join(lines)
