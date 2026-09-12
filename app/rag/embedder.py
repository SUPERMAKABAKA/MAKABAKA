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


class BedrockEmbedder:
    """基于 Amazon Bedrock 的真实 embedder，支持 Titan 与 Cohere（Req 1.2, 5.1）。

    作为 ``DeterministicEmbedder`` 的可插拔替代，通过 Bedrock Runtime 的
    ``invoke_model`` 生成文本向量。调用契约与确定性实现一致：
    ``embedder(text) -> list[float]``，可像函数一样被 ingestion 与检索复用。

    模型分派：根据 ``self.model_id`` 自动选择请求/响应格式。

    * Titan（``model_id`` 含 ``"titan"``）：
        - 请求体 ``{"inputText": text, "dimensions": dim, "normalize": True}``；
        - 响应向量取 ``json_response["embedding"]``。
    * Cohere（``model_id`` 含 ``"cohere"``，如 ``cohere.embed-multilingual-v3``）：
        - 请求体 ``{"texts": [text], "input_type": input_type,
          "embedding_types": ["float"]}``，不传 ``dimensions``（v3 固定 1024）；
        - 响应向量做健壮解析：``embeddings`` 为 dict 时取 ``["float"][0]``，
          为 list 时取 ``[0]``。

    背景：目标区域新加坡 ``ap-southeast-1`` 无 Titan Embeddings，仅有 Cohere，
    故需同时支持两种格式，按 ``model_id`` 自动分派。

    凭证不写入代码：依赖 boto3 默认凭证链。为使本模块在缺少 boto3 的环境下
    仍可被导入（不影响确定性路径），``boto3`` 采用延迟导入，仅在实例化时导入。

    注意：真实模型的输出维度（``dim``）默认 1024，与 ``DeterministicEmbedder``
    的 64 维不同。切换实现后必须重新灌库，避免同一向量库内维度不一致。
    """

    def __init__(
        self,
        model_id: str = "amazon.titan-embed-text-v2:0",
        region_name: str = "ap-southeast-1",
        dim: int = 1024,
        client=None,
        input_type: str = "search_document",
    ) -> None:
        """初始化 Bedrock embedder。

        Args:
            model_id: Bedrock embedding 模型标识。含 ``"titan"`` 走 Titan 格式，
                含 ``"cohere"`` 走 Cohere 格式，默认 Titan Text Embeddings V2。
            region_name: AWS 区域，默认新加坡 ``ap-southeast-1``。
            dim: 输出向量维度，默认 1024。Titan V2 支持 256/512/1024；Cohere
                embed-multilingual-v3 固定 1024（请求中不传该值）。
            client: 可选注入的 bedrock-runtime 客户端；为 ``None`` 时按
                ``region_name`` 创建。注入便于在测试中使用假客户端。
            input_type: 仅 Cohere 使用。灌库文档用 ``"search_document"``，
                查询可用 ``"search_query"`` 更规范，默认 ``"search_document"``。
        """
        self.model_id = model_id
        self.region_name = region_name
        self.dim = dim
        self.input_type = input_type
        if client is None:
            import boto3

            client = boto3.client("bedrock-runtime", region_name=region_name)
        self._client = client

    def _build_body(self, text: str) -> str:
        """根据 ``self.model_id`` 构造 ``invoke_model`` 请求体（JSON 字符串）。

        Args:
            text: 待向量化的文本。

        Returns:
            序列化后的请求体 JSON 字符串。

        Raises:
            ValueError: ``model_id`` 既非 Titan 也非 Cohere，无法识别格式。
        """
        import json

        model = self.model_id.lower()
        if "cohere" in model:
            # Cohere embed v3/v4 用 input_type 区分文档/查询；v3 维度固定，
            # 不传 dimensions。
            return json.dumps(
                {
                    "texts": [text],
                    "input_type": self.input_type,
                    "embedding_types": ["float"],
                }
            )
        if "titan" in model:
            return json.dumps(
                {
                    "inputText": text,
                    "dimensions": self.dim,
                    "normalize": True,
                }
            )
        raise ValueError(
            f"无法识别的 embedding model_id（既非 titan 也非 cohere）：{self.model_id}"
        )

    def _parse_vector(self, payload: dict) -> list[float]:
        """根据 ``self.model_id`` 从响应中解析出向量。

        Args:
            payload: ``invoke_model`` 响应体反序列化后的字典。

        Returns:
            向量 ``list[float]``。

        Raises:
            ValueError: ``model_id`` 无法识别，或响应结构不符合预期。
        """
        model = self.model_id.lower()
        if "cohere" in model:
            embeddings = payload["embeddings"]
            # 兼容两种 Cohere 响应：
            #   * {"embeddings": {"float": [[...]]}}（embedding_types 形态）
            #   * {"embeddings": [[...]]}（直接列表形态）
            if isinstance(embeddings, dict):
                return embeddings["float"][0]
            return embeddings[0]
        if "titan" in model:
            return payload["embedding"]
        raise ValueError(
            f"无法识别的 embedding model_id（既非 titan 也非 cohere）：{self.model_id}"
        )

    def __call__(self, text: str) -> list[float]:
        """向量化单条文本，返回长度为 ``self.dim`` 的浮点向量。

        空文本（``None`` / 空串 / 仅空白）返回全零向量，与
        ``DeterministicEmbedder`` 对空文本的行为一致，同时避免模型对空串
        报错；此路径不调用底层 client。

        Args:
            text: 待向量化的文本。

        Returns:
            向量 ``list[float]``（Titan 长度为 ``self.dim``；Cohere v3 为 1024）。

        Raises:
            RuntimeError: 调用 Bedrock 或解析响应失败时抛出，携带清晰的
                错误信息，不静默吞掉。
        """
        if not text or not text.strip():
            return [0.0] * self.dim

        import json

        try:
            response = self._client.invoke_model(
                modelId=self.model_id,
                body=self._build_body(text),
            )
            payload = json.loads(response["body"].read())
            return self._parse_vector(payload)
        except Exception as exc:  # noqa: BLE001 - 统一转换为清晰错误上抛
            raise RuntimeError(
                f"Bedrock embedding 调用失败 (model_id={self.model_id}, "
                f"region={self.region_name}): {exc}"
            ) from exc
