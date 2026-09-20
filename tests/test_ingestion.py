"""IngestionPipeline 缺字段处理的边界测试。"""

import logging

import pytest

from app.interfaces.crawler import CrawledProduct, CrawlerInterface
from app.rag.embedder import DeterministicEmbedder
from app.rag.ingestion import IngestionPipeline
from app.rag.vector_store import VectorStore


class ProductCrawler(CrawlerInterface):
    """返回指定商品的最小 CrawlerInterface 测试实现。"""

    def __init__(self, products: list[CrawledProduct]) -> None:
        self._products = products

    def fetch_products(self) -> list[CrawledProduct]:
        return self._products


def _stored_original_texts(store: VectorStore) -> set[str]:
    """读取测试内存库中的全部原始文本。"""
    results = store.query(
        DeterministicEmbedder()("boundary-test-query"),
        top_k=store.count(),
    )
    return {result.metadata["original_text"] for result in results}


@pytest.mark.parametrize(
    ("product", "missing_field", "expected_texts"),
    [
        pytest.param(
            CrawledProduct(
                product_id="missing-detail",
                source_url="https://example.com/missing-detail",
                reviews=["仍应灌入的评论一", "仍应灌入的评论二"],
            ),
            "detail",
            {"仍应灌入的评论一", "仍应灌入的评论二"},
            id="missing-detail",
        ),
        pytest.param(
            CrawledProduct(
                product_id="missing-reviews",
                source_url="https://example.com/missing-reviews",
                detail="仍应灌入的商品详情",
            ),
            "reviews",
            {"仍应灌入的商品详情"},
            id="missing-reviews",
        ),
    ],
)
def test_missing_field_is_logged_while_present_field_continues_ingesting(
    product: CrawledProduct,
    missing_field: str,
    expected_texts: set[str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """缺少单个字段时跳过该字段，记录商品标识并继续灌入现有字段。

    Validates: Requirements 1.4
    """
    store = VectorStore()
    logger = logging.getLogger(f"test.ingestion.{product.product_id}")
    pipeline = IngestionPipeline(
        crawler=ProductCrawler([product]),
        store=store,
        embedder=DeterministicEmbedder(),
        logger=logger,
    )

    with caplog.at_level(logging.INFO, logger=logger.name):
        written = pipeline.run()

    processing_logs = [
        record.getMessage() for record in caplog.records if record.name == logger.name
    ]
    assert written == len(expected_texts)
    assert store.count() == len(expected_texts)
    assert _stored_original_texts(store) == expected_texts
    assert any(
        missing_field in message and product.product_id in message
        for message in processing_logs
    )


def test_missing_detail_and_reviews_logs_both_fields_and_writes_nothing(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """详情和评论均缺失时分别记录含商品标识的日志且不写入空记录。

    Validates: Requirements 1.4
    """
    product = CrawledProduct(
        product_id="missing-both",
        source_url="https://example.com/missing-both",
    )
    store = VectorStore()
    logger = logging.getLogger("test.ingestion.missing-both")
    pipeline = IngestionPipeline(
        crawler=ProductCrawler([product]),
        store=store,
        embedder=DeterministicEmbedder(),
        logger=logger,
    )

    with caplog.at_level(logging.INFO, logger=logger.name):
        written = pipeline.run()

    processing_logs = [
        record.getMessage() for record in caplog.records if record.name == logger.name
    ]
    assert written == 0
    assert store.count() == 0
    assert len(processing_logs) == 2
    assert all(product.product_id in message for message in processing_logs)
    assert any("detail" in message for message in processing_logs)
    assert any("reviews" in message for message in processing_logs)
