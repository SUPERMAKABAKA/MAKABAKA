"""接口模拟实现的预置数据单元测试。

覆盖 MockCrawler、MockWebSearch 与 MockLLM，并验证社媒测评包含小红书、
抖音和 B 站来源。
"""

from pathlib import Path

from app.interfaces.crawler import CrawlerInterface, MockCrawler
from app.interfaces.llm import LLMInterface, MockLLM
from app.interfaces.web_search import MockWebSearch, WebSearchInterface


ROOT = Path(__file__).resolve().parents[1]


def test_mock_crawler_returns_preset_products() -> None:
    """MockCrawler 返回 products.json 中预置的商品数据。

    Validates: Requirements 1.5, 2.2
    """
    crawler = MockCrawler(str(ROOT / "data" / "products.json"))

    products = crawler.fetch_products()

    assert isinstance(crawler, CrawlerInterface)
    assert len(products) == 50
    assert products[0].model_dump() == {
        "product_id": "elec-001",
        "source_url": "https://www.amazon.cn/dp/elec-001",
        "detail": (
            "Sony WH-1000XM5 wireless noise-cancelling over-ear headphones, "
            "active noise cancellation, 30-hour battery, multipoint connection "
            "and fast charging, lightweight for all-day wear."
        ),
        "reviews": [
            "The noise cancellation is stunning; on the subway I barely hear any ambient noise.",
            "Clear sound with strong vocal detail, well worth the price.",
            "My ears don't feel stuffy even after a full day, very comfortable.",
            "A bit pricey, and the folding design isn't as portable as the previous generation.",
            "The touch controls occasionally misfire and take some getting used to.",
        ],
    }


def test_mock_web_search_returns_preset_info_and_three_platforms() -> None:
    """MockWebSearch 返回预置信息且覆盖小红书、抖音和 B 站。

    Validates: Requirements 2.2, 6.2, 6.5
    """
    web_search = MockWebSearch(str(ROOT / "data" / "web_reviews.json"))

    product_info = web_search.fetch_product_info("elec-001")
    reviews = web_search.fetch_social_reviews("elec-001")

    assert isinstance(web_search, WebSearchInterface)
    assert product_info == (
        "Sony WH-1000XM5 wireless noise-cancelling headphones is a popular item "
        "in the Electronics category. The brand highlights build quality and "
        "battery life; overall market reputation is solid, making it a focal "
        "point in its price range."
    )
    assert len(reviews) == 6
    assert reviews[0].model_dump() == {
        "platform": "xiaohongshu",
        "sentiment": "positive",
        "content": (
            "Highly recommend! This product is fantastic, the build quality "
            "exceeded my expectations, I've repurchased many times."
        ),
    }
    assert {(review.platform, review.sentiment) for review in reviews} == {
        ("xiaohongshu", "positive"),
        ("xiaohongshu", "negative"),
        ("douyin", "positive"),
        ("douyin", "negative"),
        ("bilibili", "positive"),
        ("bilibili", "negative"),
    }


def test_mock_llm_returns_preset_deterministic_response() -> None:
    """MockLLM 返回固定模板响应且不受生成参数影响。

    Validates: Requirements 2.2
    """
    llm = MockLLM()
    expected = "[MockLLM] response to: hello (sig=2cf24dba5fb0a30e)"

    assert isinstance(llm, LLMInterface)
    assert llm.generate("hello") == expected
    assert llm.generate("hello", temperature=1.0, max_tokens=1) == expected
