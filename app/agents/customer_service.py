"""基于推荐结果的离线模拟人工客服。"""

from __future__ import annotations

from app.orchestrator.models import ProductRecommendation


class CustomerService:
    """用推荐结果中的事实组织自然、可解释的客服回复。

    这里不凭空生成价格或星级：目录没有提供的字段会明确说明，并使用推荐
    理由、商品详情以及好评/差评作为人工客服的判断依据。
    """

    @staticmethod
    def answer(
        question: str,
        recommendations: list[ProductRecommendation],
    ) -> str:
        if not recommendations:
            return "您好，当前会话还没有可供咨询的推荐商品，请先完成一次商品推荐。"

        question = (question or "").strip()
        lines = [
            "您好，我已经根据本次推荐商品的详情和真实评论帮您逐项看过了。",
        ]
        if question:
            lines.append(f"您关心的是：{question}")
        lines.append("")

        for index, product in enumerate(recommendations, start=1):
            positives = product.summary.positives[:3]
            negatives = product.summary.negatives[:3]
            lines.append(f"{index}. {product.title or product.product_id}")
            lines.append(f"先说结论：{product.reason or '这件商品与当前需求匹配。'}")
            if product.detail:
                lines.append(f"商品信息：{product.detail}")
            else:
                lines.append("商品信息：当前推荐数据未提供更完整的规格描述。")

            if product.price is not None:
                lines.append(f"价格信息：{product.price}")
            else:
                lines.append("价格信息：当前商品数据未提供价格，建议打开商品页确认实时售价。")

            if product.rating is not None:
                lines.append(f"评分：{product.rating:.1f}/5")
            else:
                lines.append(
                    "评分：当前商品数据未提供官方星级；参考口碑为 "
                    f"{len(positives)} 条好评、{len(negatives)} 条差评。"
                )
            if positives:
                lines.append("用户认可：" + "；".join(positives))
            if negatives:
                lines.append("需要留意：" + "；".join(negatives))
            lines.append("")

        if len(recommendations) > 1:
            best = max(
                recommendations,
                key=lambda item: (
                    len(item.summary.positives),
                    -len(item.summary.negatives),
                ),
            )
            lines.append(
                f"如果您更看重当前评论反馈，我会优先建议「{best.title or best.product_id}」；"
                "如果您最在意价格、尺寸或某项参数，建议再结合商品页实时信息做最后决定。"
            )
        lines.append("如果您告诉我最在意的预算、功能或使用场景，我还可以继续帮您缩小选择范围。")
        return "\n".join(lines)
