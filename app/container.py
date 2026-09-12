"""依赖注入 / 装配容器。

``Container`` 依据 ``Settings`` 在启动时装配外部依赖的具体实现（爬虫 /
联网搜索 / LLM），并以抽象接口类型返回，使调用方仅依赖抽象、无需感知具体
实现（Req 2.3, 2.4）。当前各依赖仅提供模拟实现；新增真实实现时，只需在对应
映射表中增加一个分支，接口契约与调用方代码保持不变。
"""

from __future__ import annotations

from typing import Callable

from app.config import Settings, get_settings
from app.interfaces.crawler import CrawlerInterface, MockCrawler
from app.interfaces.llm import BedrockLLM, LLMInterface, MockLLM
from app.interfaces.web_search import MockWebSearch, WebSearchInterface
from app.rag.embedder import BedrockEmbedder, DeterministicEmbedder

__all__ = ["Container"]


class Container:
    """轻量依赖注入容器（Req 2.3, 2.4）。

    依据 ``Settings`` 中的实现选择，为每个外部依赖装配对应实现。所有工厂
    方法的返回类型标注为抽象接口类型，调用方据此编程，替换实现无需修改调用
    代码。
    """

    def __init__(self, settings: Settings | None = None) -> None:
        """初始化容器。

        Args:
            settings: 系统运行配置；省略时使用默认配置（``get_settings()``）。
        """
        self.settings = settings if settings is not None else get_settings()

    def crawler(self) -> CrawlerInterface:
        """按配置装配 Crawler_Interface 实现（Req 2.3, 2.4）。

        Returns:
            ``CrawlerInterface`` 实例。模拟实现读取 ``settings.products_dataset``。

        Raises:
            KeyError: ``settings.crawler_impl`` 不在支持的实现集合中时抛出。
        """
        factories = {
            "mock": lambda: MockCrawler(self.settings.products_dataset),
        }
        return factories[self.settings.crawler_impl]()

    def web_search(self) -> WebSearchInterface:
        """按配置装配 Web_Search_Interface 实现（Req 2.3, 2.4）。

        Returns:
            ``WebSearchInterface`` 实例。模拟实现读取 ``settings.web_dataset``。

        Raises:
            KeyError: ``settings.web_search_impl`` 不在支持的实现集合中时抛出。
        """
        factories = {
            "mock": lambda: MockWebSearch(self.settings.web_dataset),
        }
        return factories[self.settings.web_search_impl]()

    def llm(self) -> LLMInterface:
        """按配置装配 LLM_Interface 实现（Req 2.3, 2.4）。

        Returns:
            ``LLMInterface`` 实例。

        Raises:
            KeyError: ``settings.llm_impl`` 不在支持的实现集合中时抛出。
        """
        factories = {
            "mock": lambda: MockLLM(),
            "bedrock": lambda: BedrockLLM(
                model_id=self.settings.bedrock_llm_model_id,
                region_name=self.settings.bedrock_region,
            ),
        }
        return factories[self.settings.llm_impl]()

    def embedder(self) -> Callable[[str], list[float]]:
        """按配置装配 embedder 实现（Req 1.2, 2.3, 2.4）。

        embedder 的调用契约为 ``embedder(text) -> list[float]``，两种实现均
        以可调用对象形式满足该契约，调用方无需感知具体实现。

        Returns:
            满足 ``Callable[[str], list[float]]`` 的 embedder 实例。

        Raises:
            KeyError: ``settings.embedder_impl`` 不在支持的实现集合中时抛出。
        """
        factories = {
            "deterministic": lambda: DeterministicEmbedder(),
            "bedrock": lambda: BedrockEmbedder(
                model_id=self.settings.bedrock_embed_model_id,
                region_name=self.settings.bedrock_region,
                dim=self.settings.bedrock_embed_dim,
            ),
        }
        return factories[self.settings.embedder_impl]()
