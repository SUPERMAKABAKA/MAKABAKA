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
            return "Hi! There are no recommended products to consult about in this session yet. Please get a product recommendation first."

        question = (question or "").strip()
        lines = [
            "Hi! I've gone through each recommended product using its details and real customer reviews.",
        ]
        if question:
            lines.append(f"Your question: {question}")
        lines.append("")

        for index, product in enumerate(recommendations, start=1):
            positives = product.summary.positives[:3]
            negatives = product.summary.negatives[:3]
            lines.append(f"{index}. {product.title or product.product_id}")
            lines.append(f"Bottom line: {product.reason or 'This product matches your current needs.'}")
            if product.detail:
                lines.append(f"Product info: {product.detail}")
            else:
                lines.append("Product info: The current recommendation data does not include a fuller spec description.")

            if product.price is not None:
                lines.append(f"Price: {product.price}")
            else:
                lines.append("Price: No price in the current product data; please open the product page to confirm the live price.")

            if product.rating is not None:
                lines.append(f"Rating: {product.rating:.1f}/5")
            else:
                lines.append(
                    "Rating: No official star rating in the current product data; "
                    f"for reference: {len(positives)} positive and {len(negatives)} negative reviews."
                )
            if positives:
                lines.append("What buyers like: " + "; ".join(positives))
            if negatives:
                lines.append("Things to note: " + "; ".join(negatives))
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
                f"If you weigh current review feedback most, I'd suggest \"{best.title or best.product_id}\" first; "
                "if price, size, or a specific spec matters most to you, make the final call together with the live info on the product page."
            )
        lines.append("Tell me the budget, features, or use case you care about most, and I can help narrow the options further.")
        return "\n".join(lines)
