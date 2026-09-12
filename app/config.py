"""应用配置。

定义 ``Settings``，集中管理外部依赖的实现选择（爬虫 / 联网搜索 / LLM）、
Chroma 向量库目录以及各预置数据集路径。依赖注入容器（``app.container``）
依据这些配置在启动时装配对应实现（Req 2.3）。
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class Settings(BaseModel):
    """系统运行配置。

    Attributes:
        crawler_impl: Crawler_Interface 的实现选择，当前仅支持模拟实现。
        web_search_impl: Web_Search_Interface 的实现选择。
        llm_impl: LLM_Interface 的实现选择。
        chroma_dir: 本地 Chroma 向量库持久化目录。
        products_dataset: MockCrawler 读取的预置商品数据集路径。
        web_dataset: MockWebSearch 读取的预置社媒测评数据集路径。
        profiles_dataset: 模拟用户画像数据集路径。
    """

    # 外部依赖实现选择（Req 2.3）
    crawler_impl: Literal["mock"] = "mock"
    web_search_impl: Literal["mock"] = "mock"
    llm_impl: Literal["mock"] = "mock"

    # 向量库目录
    chroma_dir: str = ".chroma"

    # 预置数据集路径
    products_dataset: str = Field(default="data/products.json")
    web_dataset: str = Field(default="data/web_reviews.json")
    profiles_dataset: str = Field(default="data/profiles.json")


def get_settings() -> Settings:
    """返回默认配置实例。

    后续可扩展为从环境变量或配置文件加载。
    """
    return Settings()
