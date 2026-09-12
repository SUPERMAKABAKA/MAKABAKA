"""Web Search 接口抽象与模拟实现。

定义联网搜索接口契约（``WebSearchInterface``），用于获取商品的联网信息与
来自社交媒体（小红书 / 抖音 / B 站）的好评与差评测评；并提供从预置 JSON
数据集读取的模拟实现（``MockWebSearch``）。

Web_Search_Agent 通过该接口访问外部联网信息与社媒测评（Req 6.1, 6.2, 6.3），
所有外部依赖只经接口访问（Req 2.1），并为其提供一个返回预置数据的模拟实现
（Req 2.2, 6.5）。``SocialReview`` 复用自 ``app.orchestrator.session``，保持
状态载体中的数据模型一致。
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from app.orchestrator.session import SocialReview

__all__ = ["WebSearchInterface", "MockWebSearch"]


class WebSearchInterface(ABC):
    """联网搜索接口抽象，定义商品信息与社媒测评的获取契约（Req 2.1, 6.1）。

    调用方（如 Web_Search_Agent）仅依赖本抽象类型，替换实现无需修改调用代码
    （Req 2.4）。
    """

    @abstractmethod
    def fetch_product_info(self, product_id: str) -> str:
        """返回指定商品的联网信息文本（Req 6.1）。

        Args:
            product_id: 商品标识。

        Returns:
            商品的联网信息文本；无对应信息时返回空字符串。
        """
        raise NotImplementedError

    @abstractmethod
    def fetch_social_reviews(self, product_id: str) -> list[SocialReview]:
        """返回指定商品来自小红书 / 抖音 / B 站的好评与差评（Req 6.2, 6.3）。

        Args:
            product_id: 商品标识。

        Returns:
            社媒测评列表，包含 positive 与 negative 两类情感的内容；无测评时
            返回空列表（Req 6.4 由调用方据此判定 no_review）。
        """
        raise NotImplementedError


class MockWebSearch(WebSearchInterface):
    """Web_Search_Interface 的模拟实现。

    从预置的 JSON 数据集读取商品的联网信息与社媒测评，返回预置数据
    （Req 2.2, 6.5）。数据集在实例化时并不要求已存在；仅在首次调用
    ``fetch_product_info`` 或 ``fetch_social_reviews`` 时读取并缓存，若文件
    缺失或格式非法则给出清晰错误。

    数据集结构：

    ``{"info": {product_id: 信息字符串}, "reviews": {product_id: [{platform,
    sentiment, content}, ...]}}``
    """

    def __init__(self, dataset_path: str) -> None:
        """初始化模拟联网搜索。

        Args:
            dataset_path: 预置社媒测评数据集（web_reviews.json）的路径。此处不
                校验文件是否存在，读取延迟到方法调用时进行。
        """
        self._path = Path(dataset_path)
        self._info: dict[str, str] | None = None
        self._reviews: dict[str, list[SocialReview]] | None = None

    def fetch_product_info(self, product_id: str) -> str:
        """从预置数据集读取指定商品的联网信息（Req 6.1）。

        Args:
            product_id: 商品标识。

        Returns:
            商品的联网信息文本；无对应信息时返回空字符串。
        """
        self._ensure_loaded()
        assert self._info is not None
        return self._info.get(product_id, "")

    def fetch_social_reviews(self, product_id: str) -> list[SocialReview]:
        """从预置数据集读取指定商品的社媒测评（Req 6.2, 6.3）。

        Args:
            product_id: 商品标识。

        Returns:
            社媒测评列表；无对应测评时返回空列表。
        """
        self._ensure_loaded()
        assert self._reviews is not None
        return list(self._reviews.get(product_id, []))

    def _ensure_loaded(self) -> None:
        """延迟加载并解析数据集，结果缓存以避免重复读取。

        Raises:
            FileNotFoundError: 数据集文件不存在时抛出，附带路径信息。
            ValueError: 数据集不是合法 JSON，或顶层结构 / info / reviews 结构非法，
                或某条测评记录不是对象时抛出。
        """
        if self._info is not None and self._reviews is not None:
            return

        if not self._path.is_file():
            raise FileNotFoundError(
                f"社媒测评数据集不存在：{self._path}。"
                "请先生成预置数据集（data/web_reviews.json）后再运行联网搜索。"
            )

        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"社媒测评数据集不是合法 JSON：{self._path}（{exc}）"
            ) from exc

        if not isinstance(raw, dict):
            raise ValueError(
                f"社媒测评数据集顶层结构应为对象，实际为 {type(raw).__name__}：{self._path}"
            )

        self._info = self._parse_info(raw.get("info", {}))
        self._reviews = self._parse_reviews(raw.get("reviews", {}))

    def _parse_info(self, info: Any) -> dict[str, str]:
        """解析 ``info`` 段，映射 product_id 到信息字符串。

        Args:
            info: 数据集中的 ``info`` 字段。

        Returns:
            product_id 到信息字符串的映射。

        Raises:
            ValueError: ``info`` 不是对象，或某个值不是字符串时抛出。
        """
        if not isinstance(info, dict):
            raise ValueError(
                f"社媒测评数据集的 info 字段应为对象，"
                f"实际为 {type(info).__name__}：{self._path}"
            )
        parsed: dict[str, str] = {}
        for product_id, text in info.items():
            if not isinstance(text, str):
                raise ValueError(
                    f"商品 {product_id} 的联网信息应为字符串，"
                    f"实际为 {type(text).__name__}：{self._path}"
                )
            parsed[str(product_id)] = text
        return parsed

    def _parse_reviews(self, reviews: Any) -> dict[str, list[SocialReview]]:
        """解析 ``reviews`` 段，映射 product_id 到 ``SocialReview`` 列表。

        Args:
            reviews: 数据集中的 ``reviews`` 字段。

        Returns:
            product_id 到社媒测评列表的映射。

        Raises:
            ValueError: ``reviews`` 结构非法，或某条测评记录不是对象 / 字段
                非法时抛出。
        """
        if not isinstance(reviews, dict):
            raise ValueError(
                f"社媒测评数据集的 reviews 字段应为对象，"
                f"实际为 {type(reviews).__name__}：{self._path}"
            )
        parsed: dict[str, list[SocialReview]] = {}
        for product_id, items in reviews.items():
            if not isinstance(items, list):
                raise ValueError(
                    f"商品 {product_id} 的测评列表应为数组，"
                    f"实际为 {type(items).__name__}：{self._path}"
                )
            product_reviews: list[SocialReview] = []
            for index, item in enumerate(items):
                if not isinstance(item, dict):
                    raise ValueError(
                        f"商品 {product_id} 第 {index} 条测评应为对象，"
                        f"实际为 {type(item).__name__}：{self._path}"
                    )
                product_reviews.append(SocialReview.model_validate(item))
            parsed[str(product_id)] = product_reviews
        return parsed
