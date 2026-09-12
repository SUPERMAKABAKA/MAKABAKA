"""Web_Search_Agent：联网商品信息 + 社媒测评 (Req 6.1, 6.2, 6.3, 6.4)。

按 design.md 的 Agent 输入/输出契约，Web_Search_Agent 以 ``retrieval_results``
中的候选商品为输入，经 ``Web_Search_Interface`` 为每个候选获取：

- 联网商品信息（``product_info``），Req 6.1。
- 来自小红书 / 抖音 / B 站的社媒测评，同时包含好评与差评，Req 6.2, 6.3。

聚合结果写入 ``session.web_results``（每个候选一条 ``WebInfo``）。若所有候选聚合
后测评总数为 0，则置 ``session.web_status = "no_review"``（Req 6.4）；否则为
``"ok"``。候选为空（检索 no_match）时不报错：``web_results`` 为空、``web_status``
置 ``"no_review"``，流程继续。

Web_Search_Agent 仅经 ``WebSearchInterface`` 访问外部联网信息与社媒测评，符合
“外部依赖只经接口访问”的约束。任一不可恢复错误统一置
``session.error = AgentError(agent="web_search", ...)`` 供 Orchestrator 终止
（Req 8.4）。
"""

from __future__ import annotations

from app.interfaces.web_search import WebSearchInterface
from app.orchestrator.session import AgentError, ConversationSession, WebInfo

__all__ = ["WebSearchAgent"]


class WebSearchAgent:
    """为候选商品补充联网信息与社媒测评 (Req 6.1, 6.2, 6.3, 6.4)。"""

    name = "web_search"

    def __init__(self, web_search: WebSearchInterface) -> None:
        """初始化 Web_Search_Agent。

        Args:
            web_search: 联网搜索接口抽象；仅依赖接口类型，便于替换实现
                （Req 2.4）。
        """
        self._web_search = web_search

    def run(self, session: ConversationSession) -> ConversationSession:
        """为候选商品聚合联网信息与社媒测评 (Req 6.1, 6.2, 6.3, 6.4)。

        候选商品取自 ``session.retrieval_results``，按出现顺序去重 ``product_id``。
        对每个候选调用 ``fetch_product_info`` 与 ``fetch_social_reviews``，组成
        ``WebInfo`` 追加到 ``session.web_results``。聚合后若测评总数为 0，则置
        ``web_status="no_review"``，否则 ``"ok"``。

        Args:
            session: 共享会话状态，读取 ``retrieval_results``。

        Returns:
            更新后的 ``ConversationSession``：写入 ``web_results`` 与
            ``web_status``；异常时置 ``error``。
        """
        try:
            # 候选商品去重（保持首次出现顺序），检索无匹配时结果为空 (Req 6.1)
            candidate_ids: list[str] = []
            seen: set[str] = set()
            for record in session.retrieval_results:
                if record.product_id not in seen:
                    seen.add(record.product_id)
                    candidate_ids.append(record.product_id)

            web_results: list[WebInfo] = []
            total_reviews = 0
            for product_id in candidate_ids:
                product_info = self._web_search.fetch_product_info(product_id)  # Req 6.1
                social_reviews = self._web_search.fetch_social_reviews(product_id)  # Req 6.2, 6.3
                total_reviews += len(social_reviews)
                web_results.append(
                    WebInfo(
                        product_id=product_id,
                        product_info=product_info,
                        social_reviews=social_reviews,
                    )
                )

            session.web_results = web_results
            # 聚合后无任何测评（含候选为空的 no_match 情况）→ no_review (Req 6.4)
            session.web_status = "ok" if total_reviews > 0 else "no_review"
        except Exception as exc:  # noqa: BLE001 - 不可恢复错误统一传播 (Req 8.4)
            session.error = AgentError(
                agent=self.name,
                message=f"联网信息与社媒测评获取失败：{exc}",
            )

        return session
