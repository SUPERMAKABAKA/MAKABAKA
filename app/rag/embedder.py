"""确定性 embedding（离线可测）。

RAG 层需要将文本向量化后写入 / 检索向量库（Req 1.2, 5.1）。为便于离线、
可复现地测试，本模块提供一个不依赖外部模型、无需联网下载的确定性
embedding 实现：相同文本恒定映射到同一固定维度的浮点向量。

实现思路：基于字符 n-gram 的哈希，将文本散列到固定维度的桶中累加权重，
再做 L2 归一化。该方案可插拔替换为真实 embedding 模型，调用契约保持为
``Callable[[str], list[float]]``。
"""

from __future__ import annotations

import hashlib
import math

# 默认向量维度。维度固定以保证同一向量库内向量长度一致。
DEFAULT_DIM = 64


def _hash_to_bucket(token: str, dim: int) -> tuple[int, float]:
    """将单个 token 稳定映射到 (桶下标, 带符号权重)。

    使用 md5 摘要的字节生成确定性的桶下标与符号，避免依赖 Python 进程级
    的 ``hash()`` 随机化（PYTHONHASHSEED），从而保证跨进程可复现。

    Args:
        token: 待散列的文本片段。
        dim: 向量维度。

    Returns:
        (bucket_index, signed_weight) 二元组。
    """
    digest = hashlib.md5(token.encode("utf-8")).digest()
    bucket = int.from_bytes(digest[:4], "big") % dim
    # 用第 5 个字节的最低位决定符号，减少不同 token 相互抵消导致的信息损失。
    sign = 1.0 if digest[4] & 1 else -1.0
    return bucket, sign


def embed(text: str, dim: int = DEFAULT_DIM) -> list[float]:
    """将文本确定性地映射为固定维度的浮点向量（Req 1.2, 5.1）。

    对同一文本多次调用返回完全一致的向量；不依赖任何外部模型或网络。

    Args:
        text: 待向量化的文本。
        dim: 输出向量维度，默认为 :data:`DEFAULT_DIM`。

    Returns:
        长度为 ``dim`` 的浮点数列表。空文本返回全零向量。
    """
    vec = [0.0] * dim
    if not text:
        return vec

    normalized = text.strip().lower()
    if not normalized:
        return vec

    # 以字符三元组（含边界）作为特征，兼顾中英文且无需分词。
    padded = f"  {normalized}  "
    for i in range(len(padded) - 2):
        gram = padded[i : i + 3]
        bucket, sign = _hash_to_bucket(gram, dim)
        vec[bucket] += sign

    # L2 归一化，使相似度检索只反映方向差异。
    norm = math.sqrt(sum(v * v for v in vec))
    if norm > 0.0:
        vec = [v / norm for v in vec]
    return vec


class DeterministicEmbedder:
    """可调用的确定性 embedder 封装。

    以对象形式持有维度配置，便于依赖注入；调用契约为
    ``embedder(text) -> list[float]``，与设计文档中 ``self._embed(chunk)``
    的用法一致。
    """

    def __init__(self, dim: int = DEFAULT_DIM) -> None:
        """初始化 embedder。

        Args:
            dim: 输出向量维度。
        """
        self.dim = dim

    def __call__(self, text: str) -> list[float]:
        """向量化单条文本。

        Args:
            text: 待向量化的文本。

        Returns:
            长度为 ``self.dim`` 的浮点向量。
        """
        return embed(text, self.dim)
