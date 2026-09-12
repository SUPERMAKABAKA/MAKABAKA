"""Chroma 向量库封装。

对 ``chromadb`` 做薄封装，向上层（Ingestion_Pipeline、Retrieval_Agent）提供
稳定的 ``add`` / ``query`` 契约（Req 1.2, 5.1）：

- ``add(embedding, metadata)``：写入一条已向量化的记录及其元数据。
- ``query(embedding, top_k)``：按向量相似度检索，返回含 ``metadata`` 与
  ``distance`` 的结果对象列表。

由于上层使用自定义确定性 embedding（见 :mod:`app.rag.embedder`），本封装在
add/query 时直接向 Chroma 传入向量，不使用 Chroma 的默认 embedding function，
避免其尝试下载 / 加载模型。
"""

from __future__ import annotations

import uuid
from typing import Any, NamedTuple, Optional

import chromadb


class QueryResult(NamedTuple):
    """单条检索结果。

    字段命名与调用方约定一致：Retrieval_Agent 通过 ``h.metadata[...]`` 读取
    product_id / source_url / original_text，通过 ``h.distance`` 计算相关度。

    Attributes:
        metadata: 写入时保存的元数据字典（含 product_id、source_url、
            original_text 等，见 Req 1.3）。
        distance: 查询向量与该记录向量的距离，越小越相关。
    """

    metadata: dict[str, Any]
    distance: float


class VectorStore:
    """Chroma 集合的封装。

    默认使用持久化客户端将数据写入本地目录；若未提供目录则使用内存
    （Ephemeral）客户端，便于测试而不污染项目。
    """

    def __init__(
        self,
        chroma_dir: Optional[str] = None,
        collection: str = "products",
    ) -> None:
        """初始化向量库。

        Args:
            chroma_dir: Chroma 持久化目录；为 ``None`` 时使用内存客户端。
            collection: 集合名称。
        """
        if chroma_dir:
            self._client = chromadb.PersistentClient(path=chroma_dir)
            collection_name = collection
        else:
            # 内存客户端在同一进程内按集合名共享状态，为保证多个内存实例
            # （尤其是测试）相互隔离，为每个实例生成唯一集合名。
            self._client = chromadb.EphemeralClient()
            collection_name = f"{collection}-{uuid.uuid4().hex}"

        # 显式关闭默认 embedding function：本封装只接收外部预计算的向量。
        self._collection = self._client.get_or_create_collection(
            name=collection_name,
            embedding_function=None,
            metadata={"hnsw:space": "cosine"},
        )

    def add(self, embedding: list[float], metadata: dict[str, Any]) -> str:
        """写入一条已向量化的记录。

        Args:
            embedding: 记录对应的向量（由外部 embedder 生成）。
            metadata: 记录的元数据（至少含 product_id、source_url、
                original_text，见 Req 1.3）。

        Returns:
            自动生成的记录唯一 id。
        """
        record_id = uuid.uuid4().hex
        self._collection.add(
            ids=[record_id],
            embeddings=[embedding],
            metadatas=[metadata],
        )
        return record_id

    def query(self, embedding: list[float], top_k: int = 20) -> list[QueryResult]:
        """按向量相似度检索最相近的若干条记录（Req 5.1）。

        Args:
            embedding: 查询向量。
            top_k: 返回的最大结果数。

        Returns:
            :class:`QueryResult` 列表，每项含 ``metadata`` 与 ``distance``；
            集合为空时返回空列表。
        """
        # 集合为空时直接返回，避免 Chroma 在无数据时的边界行为。
        if self._collection.count() == 0:
            return []

        n_results = min(top_k, self._collection.count())
        raw = self._collection.query(
            query_embeddings=[embedding],
            n_results=n_results,
            include=["metadatas", "distances"],
        )

        # Chroma 对 query 返回按查询批次嵌套的列表，这里只有一个查询向量。
        metadatas = (raw.get("metadatas") or [[]])[0]
        distances = (raw.get("distances") or [[]])[0]

        results: list[QueryResult] = []
        for meta, dist in zip(metadatas, distances):
            results.append(
                QueryResult(metadata=dict(meta or {}), distance=float(dist))
            )
        return results

    def count(self) -> int:
        """返回集合中记录总数。"""
        return self._collection.count()
