"""数据灌库脚本（Ingestion 入口）。

通过依赖注入容器（``Container``）装配爬虫、向量库与 embedder，并运行
``IngestionPipeline`` 将预置商品详情与评论写入本地 Chroma 向量库，为 RAG
检索建立数据基础（Req 1.1）。

用法::

    python -m scripts.ingest

向量库持久化到 ``Settings.chroma_dir``（默认 ``.chroma``）。日志级别为
INFO，便于观察缺字段跳过的处理日志（见 IngestionPipeline，Req 1.4）。
"""

from __future__ import annotations

import logging

from app.config import get_settings
from app.container import Container
from app.rag.embedder import DeterministicEmbedder
from app.rag.ingestion import IngestionPipeline
from app.rag.vector_store import VectorStore


def main() -> int:
    """装配组件并运行灌库流程，返回写入的记录数（Req 1.1）。

    以默认配置构造 ``Container`` 装配爬虫，向量库持久化到
    ``settings.chroma_dir``，使用确定性 embedder；运行 ``IngestionPipeline``
    后打印写入记录数。

    Returns:
        成功写入向量库的记录（chunk）总数。
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    logger = logging.getLogger("ingest")

    settings = get_settings()
    container = Container(settings)

    crawler = container.crawler()
    store = VectorStore(chroma_dir=settings.chroma_dir)
    embedder = DeterministicEmbedder()

    pipeline = IngestionPipeline(
        crawler=crawler,
        store=store,
        embedder=embedder,
        logger=logger,
    )

    written = pipeline.run()
    logger.info("灌库完成，写入记录数=%d", written)
    print(f"写入记录数: {written}")
    return written


if __name__ == "__main__":
    main()
