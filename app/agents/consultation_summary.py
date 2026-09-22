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
        titles = "、".join(
            (item.title or item.product_id) for item in recommendations
        )
        return (
            "你是购物助手。请仅基于下面这段客服咨询内容做要点总结，"
            "不要新增任何价格、星级或原文中不存在的事实。"
            "输出简明中文，覆盖推荐倾向、主要优点、需要留意之处。\n"
            f"涉及商品：{titles}\n"
            "客服咨询内容：\n"
            f"{transcript}\n"
            "请给出总结："
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
                return "客服要点总结：\n" + text
            return "暂无可总结的客服咨询内容，请先获取推荐并发起咨询。"

        lines: list[str] = ["以下是本次客服咨询的要点总结："]
        for index, product in enumerate(recommendations, start=1):
            name = product.title or product.product_id
            reason = (product.reason or "").strip() or "与当前需求匹配。"
            positives = [p for p in product.summary.positives[:2] if p]
            negatives = [n for n in product.summary.negatives[:2] if n]
            parts = [f"{index}. {name}：推荐倾向——{reason}"]
            if positives:
                parts.append("主要优点：" + "；".join(positives))
            if negatives:
                parts.append("需要留意：" + "；".join(negatives))
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
                f"综合口碑，我会优先建议「{best.title or best.product_id}」，"
                "最终请结合商品页实时信息决定。"
            )
        return "\n".join(lines)
