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
            "索尼 WH-1000XM5 无线降噪头戴式耳机，主动降噪，30 小时续航，"
            "支持多点连接与快充，佩戴轻盈适合长时间使用。"
        ),
        "reviews": [
            "降噪效果非常惊艳，地铁上几乎听不到环境噪音。",
            "音质通透，人声解析力强，值得这个价位。",
            "佩戴一整天耳朵也不闷，非常舒适。",
            "价格偏贵，折叠结构不如上一代方便携带。",
            "触控操作偶尔会误触，需要适应一段时间。",
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
        "索尼 WH-1000XM5 无线降噪头戴属于数码电子品类的热门单品，"
        "官方主打做工与续航，市场口碑整体不错，是同价位段的关注热点。"
    )
    assert len(reviews) == 6
    assert reviews[0].model_dump() == {
        "platform": "xiaohongshu",
        "sentiment": "positive",
        "content": "姐妹们冲！这款数码电子产品真的绝，做工超出预期，回购无数次。",
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
