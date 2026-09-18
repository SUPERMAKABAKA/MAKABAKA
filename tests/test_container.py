"""Container 装配与接口实现可替换性单元测试。"""

from pathlib import Path

from app.config import Settings
from app.container import Container
from app.interfaces.crawler import CrawlerInterface, MockCrawler
from app.interfaces.llm import LLMInterface, MockLLM
from app.interfaces.web_search import MockWebSearch, WebSearchInterface


ROOT = Path(__file__).resolve().parents[1]


class ReplacementLLM(LLMInterface):
    """满足 LLMInterface 契约的测试替代实现。"""

    def generate(self, prompt: str, **kw) -> str:
        return f"replacement response to: {prompt}"


class ReplacementLLMContainer(Container):
    """仅替换 LLM 具体实现，保持 Container 对调用方的契约不变。"""

    def llm(self) -> LLMInterface:
        return ReplacementLLM()


def _generate_response(container: Container, prompt: str) -> str:
    """模拟只通过 Container 和 LLMInterface 使用依赖的调用方。"""
    return container.llm().generate(prompt)


def test_container_assembles_mock_implementations_from_settings() -> None:
    """Settings 指定 mock 时，Container 装配对应模拟实现。

    Validates: Requirements 2.3
    """
    settings = Settings(
        crawler_impl="mock",
        web_search_impl="mock",
        llm_impl="mock",
        products_dataset=str(ROOT / "data" / "products.json"),
        web_dataset=str(ROOT / "data" / "web_reviews.json"),
    )

    container = Container(settings)
    crawler = container.crawler()
    web_search = container.web_search()
    llm = container.llm()

    assert isinstance(crawler, CrawlerInterface)
    assert isinstance(crawler, MockCrawler)
    assert isinstance(web_search, WebSearchInterface)
    assert isinstance(web_search, MockWebSearch)
    assert isinstance(llm, LLMInterface)
    assert isinstance(llm, MockLLM)


def test_conforming_implementation_can_be_replaced_without_caller_changes() -> None:
    """替换为同契约实现后，同一调用方函数无需修改即可工作。

    Validates: Requirements 2.4
    """
    settings = Settings(llm_impl="mock")
    mock_container = Container(settings)
    replacement_container = ReplacementLLMContainer(settings)

    mock_result = _generate_response(mock_container, "compare headphones")
    replacement_result = _generate_response(
        replacement_container, "compare headphones"
    )

    assert mock_result.startswith("[MockLLM] response to: compare headphones")
    assert replacement_result == "replacement response to: compare headphones"
    assert isinstance(replacement_container.llm(), LLMInterface)
