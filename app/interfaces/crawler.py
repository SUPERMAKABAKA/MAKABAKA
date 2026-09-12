"""Crawler 接口抽象与模拟实现。

定义爬虫接口契约（``CrawlerInterface``）及其数据模型（``CrawledProduct``），
并提供从预置 JSON 数据集读取约 50 种商品的模拟实现（``MockCrawler``）。

Assistant_System 通过该接口访问商品评论与详情等外部依赖（Req 2.1），
并为其提供一个模拟实现返回预置数据（Req 1.5, 2.2）。Ingestion_Pipeline
借助该接口读取商品数据灌入向量库（Req 1.1）。
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel, Field


class CrawledProduct(BaseModel):
    """单条爬取到的商品数据。

    Attributes:
        product_id: 商品标识，作为写入 Vector_Store 记录的元数据（Req 1.3）。
        source_url: 商品来源链接，作为元数据保留（Req 1.3）。
        detail: 商品详情文本，可缺失（Req 1.4）。
        reviews: 商品评论文本列表，可为空（Req 1.4）。
    """

    product_id: str
    source_url: str
    detail: Optional[str] = None
    reviews: list[str] = Field(default_factory=list)


class CrawlerInterface(ABC):
    """爬虫接口抽象，定义商品评论与详情的获取契约（Req 2.1）。

    调用方（如 Ingestion_Pipeline）仅依赖本抽象类型，替换实现无需修改
    调用代码（Req 2.4）。
    """

    @abstractmethod
    def fetch_products(self) -> list[CrawledProduct]:
        """返回商品评论与详情数据（Req 1.1）。

        Returns:
            爬取到的商品列表。
        """
        raise NotImplementedError


class MockCrawler(CrawlerInterface):
    """Crawler_Interface 的模拟实现。

    从预置的 JSON 数据集读取约 50 种商品的评论与详情，返回预置数据
    （Req 1.5, 2.2）。数据集在实例化时并不要求已存在；仅在调用
    ``fetch_products`` 时读取，若文件缺失或格式非法则给出清晰错误。
    """

    def __init__(self, dataset_path: str) -> None:
        """初始化模拟爬虫。

        Args:
            dataset_path: 预置商品数据集（products.json）的路径。此处不校验
                文件是否存在，读取延迟到 ``fetch_products`` 调用时进行。
        """
        self._path = Path(dataset_path)

    def fetch_products(self) -> list[CrawledProduct]:
        """从预置数据集读取并解析商品列表（Req 1.1, 1.5）。

        Returns:
            解析后的 ``CrawledProduct`` 列表。

        Raises:
            FileNotFoundError: 数据集文件不存在时抛出，附带路径信息。
            ValueError: 数据集不是合法 JSON，或顶层结构不是商品数组，
                或某条记录不是对象时抛出。
        """
        if not self._path.is_file():
            raise FileNotFoundError(
                f"商品数据集不存在：{self._path}。"
                "请先生成预置数据集（data/products.json）后再运行灌库流程。"
            )

        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"商品数据集不是合法 JSON：{self._path}（{exc}）"
            ) from exc

        if not isinstance(raw, list):
            raise ValueError(
                f"商品数据集顶层结构应为数组，实际为 {type(raw).__name__}：{self._path}"
            )

        products: list[CrawledProduct] = []
        for index, item in enumerate(raw):
            if not isinstance(item, dict):
                raise ValueError(
                    f"商品数据集第 {index} 条记录应为对象，"
                    f"实际为 {type(item).__name__}：{self._path}"
                )
            products.append(self._parse_product(item))
        return products

    @staticmethod
    def _parse_product(item: dict[str, Any]) -> CrawledProduct:
        """将单条 JSON 记录解析为 ``CrawledProduct``。

        Args:
            item: 单条商品的 JSON 对象。

        Returns:
            解析后的商品模型。

        Raises:
            ValueError: 记录缺少必填字段或字段类型非法时抛出。
        """
        return CrawledProduct.model_validate(item)
