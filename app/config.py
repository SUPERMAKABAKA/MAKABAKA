"""应用配置。

定义 ``Settings``，集中管理外部依赖的实现选择（爬虫 / 联网搜索 / LLM）、
Chroma 向量库目录以及各预置数据集路径。依赖注入容器（``app.container``）
依据这些配置在启动时装配对应实现（Req 2.3）。
"""

from __future__ import annotations

import os
from typing import Literal

from pydantic import BaseModel, Field

# 模块导入时自动加载项目根目录的 .env（若存在），方便团队成员各自在 .env
# 中填入自己的 AWS 凭证与实现选择，而无需修改代码或设置系统环境变量。
# 说明：
#   * python-dotenv 采用 try import，未安装时静默跳过，保证不硬依赖；
#   * load_dotenv 默认 override=False，即已存在的真实环境变量优先，.env 仅
#     作为补充，这是期望行为（系统环境变量 > .env > 代码默认值）。
try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # pragma: no cover - 未安装 dotenv 时降级为不加载 .env
    pass


class Settings(BaseModel):
    """系统运行配置。

    Attributes:
        crawler_impl: Crawler_Interface 的实现选择，当前仅支持模拟实现。
        web_search_impl: Web_Search_Interface 的实现选择。
        llm_impl: LLM_Interface 的实现选择（mock / bedrock）。
        embedder_impl: embedder 的实现选择（deterministic / bedrock）。
        chroma_dir: 本地 Chroma 向量库持久化目录。
        products_dataset: MockCrawler 读取的预置商品数据集路径。
        web_dataset: MockWebSearch 读取的预置社媒测评数据集路径。
        profiles_dataset: 模拟用户画像数据集路径。
        bedrock_region: Bedrock 调用所用 AWS 区域。
        bedrock_llm_model_id: Bedrock LLM 模型标识。
        bedrock_embed_model_id: Bedrock embedding 模型标识。
        bedrock_embed_dim: Bedrock embedding 输出维度。
    """

    # 外部依赖实现选择（Req 2.3）
    crawler_impl: Literal["mock"] = "mock"
    web_search_impl: Literal["mock"] = "mock"
    llm_impl: Literal["mock", "bedrock"] = "mock"
    embedder_impl: Literal["deterministic", "bedrock"] = "deterministic"

    # 向量库目录
    chroma_dir: str = ".chroma"

    # 预置数据集路径
    products_dataset: str = Field(default="data/products.json")
    web_dataset: str = Field(default="data/web_reviews.json")
    profiles_dataset: str = Field(default="data/profiles.json")

    # Amazon Bedrock 配置（真实实现使用；区域默认新加坡）
    bedrock_region: str = "ap-southeast-1"
    bedrock_llm_model_id: str = "amazon.nova-lite-v1:0"
    bedrock_embed_model_id: str = "amazon.titan-embed-text-v2:0"
    bedrock_embed_dim: int = 1024


def get_settings() -> Settings:
    """返回配置实例，支持环境变量覆盖实现选择。

    默认保持向后兼容（``mock`` + ``deterministic``）。可通过环境变量
    ``LLM_IMPL`` 与 ``EMBEDDER_IMPL`` 切换实现，从而无需改代码即可在
    mock 与 bedrock 之间切换。仅当环境变量有值时才覆盖对应默认。

    Bedrock 相关配置也支持环境变量覆盖：
      * 区域：``AWS_REGION`` 优先，其次 ``BEDROCK_REGION``；
      * LLM 模型：``BEDROCK_LLM_MODEL_ID``；
      * embedding 模型：``BEDROCK_EMBED_MODEL_ID``；
      * embedding 维度：``BEDROCK_EMBED_DIM``（转为 int）。

    这些环境变量在模块导入时已由 ``load_dotenv()`` 从 .env 合并进
    ``os.environ``（系统环境变量优先），因此团队成员各自填 .env 即可。
    """
    overrides: dict[str, object] = {}

    llm_impl = os.environ.get("LLM_IMPL")
    if llm_impl:
        overrides["llm_impl"] = llm_impl
    embedder_impl = os.environ.get("EMBEDDER_IMPL")
    if embedder_impl:
        overrides["embedder_impl"] = embedder_impl

    # 区域：AWS_REGION 优先（与 boto3 默认凭证链使用的变量一致），其次
    # BEDROCK_REGION，二者皆无则沿用默认。
    bedrock_region = os.environ.get("AWS_REGION") or os.environ.get(
        "BEDROCK_REGION"
    )
    if bedrock_region:
        overrides["bedrock_region"] = bedrock_region

    llm_model_id = os.environ.get("BEDROCK_LLM_MODEL_ID")
    if llm_model_id:
        overrides["bedrock_llm_model_id"] = llm_model_id
    embed_model_id = os.environ.get("BEDROCK_EMBED_MODEL_ID")
    if embed_model_id:
        overrides["bedrock_embed_model_id"] = embed_model_id

    embed_dim = os.environ.get("BEDROCK_EMBED_DIM")
    if embed_dim:
        # 环境变量恒为字符串，维度需转为 int；非法值直接抛出以尽早暴露配置错误。
        overrides["bedrock_embed_dim"] = int(embed_dim)

    return Settings(**overrides)
