"""LLM 接口抽象与模拟实现。

本模块定义大语言模型的接口契约 (``LLMInterface``) 以及一个基于模板的
确定性模拟实现 (``MockLLM``)。模拟实现对相同输入始终产生相同输出，便于
离线测试与可复现的编排流程。

相关需求：2.1（外部依赖经接口访问）、2.2（每个接口提供模拟实现）。
"""

from __future__ import annotations

import hashlib
from abc import ABC, abstractmethod

__all__ = ["LLMInterface", "MockLLM", "BedrockLLM"]


class LLMInterface(ABC):
    """大语言模型接口契约。

    所有调用方仅依赖本抽象类型，从而使真实实现与模拟实现可互相替换
    （Req 2.1, 2.4）。
    """

    @abstractmethod
    def generate(self, prompt: str, **kw) -> str:
        """依据 ``prompt`` 生成文本。

        Args:
            prompt: 提示词文本。
            **kw: 实现相关的可选生成参数（如温度、最大长度等）。

        Returns:
            生成的文本字符串。
        """
        raise NotImplementedError


class MockLLM(LLMInterface):
    """基于模板的确定性 LLM 模拟实现（Req 2.2）。

    ``generate`` 的输出仅由 ``prompt`` 决定：相同的 ``prompt`` 永远返回
    相同的字符串，不受调用次数或额外关键字参数影响。这保证了测试的可
    复现性，无需依赖真实的大语言模型服务。
    """

    _TEMPLATE = "[MockLLM] response to: {summary} (sig={signature})"

    def generate(self, prompt: str, **kw) -> str:
        """返回对 ``prompt`` 的确定性模板化响应。

        Args:
            prompt: 提示词文本。
            **kw: 被忽略，仅为满足接口契约而接收。

        Returns:
            由 ``prompt`` 唯一决定的字符串。
        """
        return self._template_response(prompt)

    @classmethod
    def _template_response(cls, prompt: str) -> str:
        """基于 ``prompt`` 构造确定性模板响应。"""
        text = "" if prompt is None else str(prompt)
        signature = hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]
        summary = cls._summarize(text)
        return cls._TEMPLATE.format(summary=summary, signature=signature)

    @staticmethod
    def _summarize(text: str) -> str:
        """将提示词压缩为简短、稳定的摘要片段。"""
        collapsed = " ".join(text.split())
        max_len = 60
        if len(collapsed) <= max_len:
            return collapsed
        return collapsed[:max_len] + "..."


class BedrockLLM(LLMInterface):
    """基于 Amazon Bedrock 的真实 LLM 实现（Req 2.1）。

    作为 ``MockLLM`` 的可插拔替代，通过 Bedrock Runtime 的 Converse API 调用
    托管大语言模型。Converse API 对不同底层模型提供统一的请求 / 响应结构，
    因此切换 ``model_id`` 无需改动调用逻辑。

    凭证不写入代码：依赖 boto3 默认凭证链（环境变量、共享配置文件、IAM 角色
    等）。为使本模块在缺少 boto3 的环境下仍可被导入（不影响 Mock 路径），
    ``boto3`` 采用延迟导入，仅在实例化时导入。
    """

    def __init__(
        self,
        model_id: str = "amazon.nova-lite-v1:0",
        region_name: str = "ap-southeast-1",
        client=None,
    ) -> None:
        """初始化 Bedrock LLM 客户端。

        Args:
            model_id: Bedrock 模型标识，默认 Amazon Nova Lite。
            region_name: AWS 区域，默认新加坡 ``ap-southeast-1``。
            client: 可选注入的 bedrock-runtime 客户端；为 ``None`` 时按
                ``region_name`` 创建。注入便于在测试中使用假客户端。
        """
        self.model_id = model_id
        self.region_name = region_name
        if client is None:
            import boto3

            client = boto3.client("bedrock-runtime", region_name=region_name)
        self._client = client

    def generate(self, prompt: str, **kw) -> str:
        """调用 Bedrock Converse API 依据 ``prompt`` 生成文本。

        Args:
            prompt: 提示词文本。
            **kw: 可选生成参数，支持 ``max_tokens``（默认 512）与
                ``temperature``（默认 0.7）。

        Returns:
            模型生成的文本字符串。

        Raises:
            RuntimeError: 调用 Bedrock 或解析响应失败时抛出，携带清晰的
                错误信息，交由上层 Agent 的 try/except 捕获并置入
                ``session.error``（不静默吞掉）。
        """
        try:
            response = self._client.converse(
                modelId=self.model_id,
                messages=[
                    {"role": "user", "content": [{"text": prompt}]}
                ],
                inferenceConfig={
                    "maxTokens": kw.get("max_tokens", 512),
                    "temperature": kw.get("temperature", 0.7),
                },
            )
            return response["output"]["message"]["content"][0]["text"]
        except Exception as exc:  # noqa: BLE001 - 统一转换为清晰错误上抛
            raise RuntimeError(
                f"Bedrock LLM 调用失败 (model_id={self.model_id}, "
                f"region={self.region_name}): {exc}"
            ) from exc
