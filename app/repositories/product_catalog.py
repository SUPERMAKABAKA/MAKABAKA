"""本地商品目录读取器。

推荐结果和模拟客服都从同一份商品数据读取详情、价格、评分与评论，避免
推荐卡片和客服回答使用两套不一致的数据。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field


class CatalogProduct(BaseModel):
    """商品目录中的可选扩展字段。旧数据没有价格/评分时保持为 ``None``。"""

    product_id: str
    source_url: str = ""
    detail: str = ""
    reviews: list[str] = Field(default_factory=list)
    price: Optional[str | float] = None
    rating: Optional[float] = None


class ProductCatalog:
    """延迟加载并按商品 ID 提供本地商品数据。"""

    def __init__(self, dataset_path: str) -> None:
        self._path = Path(dataset_path)
        self._products: dict[str, CatalogProduct] | None = None

    def get(self, product_id: str) -> CatalogProduct | None:
        self._ensure_loaded()
        assert self._products is not None
        return self._products.get(product_id)

    def find_by_terms(self, terms: list[str]) -> list[CatalogProduct]:
        """返回详情中包含任一关键词的商品，保持数据集原始顺序。"""
        self._ensure_loaded()
        assert self._products is not None
        if not terms:
            return []
        matched: list[CatalogProduct] = []
        for product in self._products.values():
            haystack = product.detail or ""
            if any(term in haystack for term in terms):
                matched.append(product)
        return matched

    def _ensure_loaded(self) -> None:
        if self._products is not None:
            return
        if not self._path.is_file():
            raise FileNotFoundError(f"商品数据集不存在：{self._path}")
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"商品数据集不是合法 JSON：{self._path}") from exc
        if not isinstance(raw, list):
            raise ValueError(f"商品数据集顶层结构应为数组：{self._path}")

        products: dict[str, CatalogProduct] = {}
        for index, item in enumerate(raw):
            if not isinstance(item, dict):
                raise ValueError(f"商品数据集第 {index} 条记录应为对象：{self._path}")
            product = CatalogProduct.model_validate(item)
            products[product.product_id] = product
        self._products = products
