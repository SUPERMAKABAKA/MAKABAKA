"""数据灌库流程（Ingestion_Pipeline）。

将预爬取的商品详情与评论处理并写入向量库，为 RAG 检索建立数据基础
（Req 1.1–1.4）。流程遵循 design.md 中 "Ingestion Pipeline（数据灌库流程）"
章节：

1. **爬取**：经 ``CrawlerInterface.fetch_products()`` 读取约 50 种商品
   （模拟实现返回预置数据，Req 1.1）。
2. **字段校验**：对每条商品分别处理 ``detail`` 与 ``reviews``；缺失字段
   跳过并记录一条含 ``product_id`` 的处理日志（Req 1.4）。
3. **文本切分**：将 detail 与每条 review 切分为待向量化的 chunk。对本阶段
   的模拟数据，每条 detail / review 直接作为一个 chunk（简单稳妥）。
4. **向量化**：通过可插拔的 embedder（``Callable[[str], list[float]]``）
   生成向量（Req 1.2）。
5. **写入向量库**：每个 chunk 作为一条记录写入，metadata 至少含
   ``product_id``、``source_url``、``original_text``（Req 1.3）。

调用方仅依赖抽象类型（``CrawlerInterface``）与稳定契约（``VectorStore.add``、
embedder 可调用），替换实现无需修改本流程（Req 2.4）。
"""

from __future__ import annotations

import logging
from typing import Callable

from app.interfaces.crawler import CrawlerInterface
from app.rag.vector_store import VectorStore

# embedder 契约：文本 -> 向量。与 :mod:`app.rag.embedder` 的
# ``DeterministicEmbedder``/``embed`` 一致。
Embedder = Callable[[str], list[float]]


class IngestionPipeline:
    """把商品详情与评论灌入向量库的流程编排。

    组合爬虫、向量库、embedder 与日志器；``run`` 执行完整的
    读取 → 校验 → 切分 → 向量化 → 写入流程。
    """

    def __init__(
        self,
        crawler: CrawlerInterface,
        store: VectorStore,
        embedder: Embedder,
        logger: logging.Logger,
    ) -> None:
        """初始化灌库流程。

        Args:
            crawler: 商品数据来源，经其读取待灌库的商品（Req 1.1）。
            store: 目标向量库，提供 ``add(embedding, metadata)`` 契约。
            embedder: 文本向量化可调用，签名 ``(text) -> list[float]``（Req 1.2）。
            logger: 标准库日志器，用于记录缺字段跳过的处理日志（Req 1.4）。
        """
        self._crawler = crawler
        self._store = store
        self._embed = embedder
        self._log = logger

    def run(self) -> int:
        """执行灌库流程并返回写入向量库的记录数（Req 1.1–1.4）。

        对每条商品：``detail`` 存在则纳入待处理文本，否则记录跳过日志；
        ``reviews`` 非空则纳入，否则记录跳过日志。随后将文本切分为 chunk，
        逐个向量化并写入向量库，每条记录携带 product_id / source_url /
        original_text 元数据。

        Returns:
            成功写入向量库的记录（chunk）总数。
        """
        written = 0
        for product in self._crawler.fetch_products():
            texts: list[str] = []

            # detail：缺失则跳过该字段并记录含 product_id 的日志（Req 1.4）。
            if product.detail:
                texts.append(product.detail)
            else:
                self._log.info(
                    "跳过缺失的 detail 字段 product_id=%s", product.product_id
                )

            # reviews：为空则跳过该字段并记录含 product_id 的日志（Req 1.4）。
            if product.reviews:
                texts.extend(product.reviews)
            else:
                self._log.info(
                    "跳过缺失的 reviews 字段 product_id=%s", product.product_id
                )

            for chunk in self._chunk(texts):
                self._store.add(
                    embedding=self._embed(chunk),
                    metadata={
                        "product_id": product.product_id,
                        "source_url": product.source_url,
                        "original_text": chunk,  # Req 1.3
                        # 让检索结果能够把完整商品信息传递给推荐与客服。
                        "detail": product.detail or "",
                    },
                )
                written += 1

        return written

    @staticmethod
    def _chunk(texts: list[str]) -> list[str]:
        """将待处理文本切分为向量化用的 chunk。

        本阶段针对模拟数据采用最简策略：每条 detail / review 作为一个
        chunk，仅去除首尾空白并过滤空串，保证不写入无意义的空向量记录。

        Args:
            texts: 待切分的文本列表（detail 与各条 review）。

        Returns:
            清洗后的 chunk 列表。
        """
        chunks: list[str] = []
        for text in texts:
            if text is None:
                continue
            stripped = text.strip()
            if stripped:
                chunks.append(stripped)
        return chunks
