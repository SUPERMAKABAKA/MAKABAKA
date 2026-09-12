"""LLM 接口抽象与模拟实现。

本模块定义大语言模型的接口契约 (``LLMInterface``) 以及一个基于模板的
确定性模拟实现 (``MockLLM``)。模拟实现对相同输入始终产生相同输出，便于
离线测试与可复现的编排流程。

相关需求：2.1（外部依赖经接口访问）、2.2（每个接口提供模拟实现）。
"""

from __future__ import annotations

import hashlib
import json
import urllib.error
import urllib.request
from abc import ABC, abstractmethod

__all__ = ["LLMInterface", "MockLLM", "BedrockLLM", "GeminiLLM"]


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


class GeminiLLM(LLMInterface):
    """基于 Google AI Studio (Gemini) 的真实 LLM 实现（Req 2.1）。

    作为 ``MockLLM`` / ``BedrockLLM`` 之外的可插拔选项，通过 Gemini 的
    ``generateContent`` REST 端点调用托管大语言模型，用于在无法使用 Bedrock
    （配额 / 开通问题）时生成推荐理由。

    实现仅依赖标准库（``urllib`` / ``json``），不引入新的第三方依赖。API Key
    不写入代码，由上层从环境变量 ``GEMINI_API_KEY`` 注入。

    健壮性约定：
      * 当响应结构缺失或被安全过滤（无 ``candidates`` 或无 ``text``）时，
        ``generate`` 返回空字符串，交由上层走兜底模板，不抛异常导致整个流程
        500；
      * 当网络错误或 HTTP 4xx/5xx 时，抛出 ``RuntimeError``（携带状态码与响应
        体前 200 字），交由上层 Agent 捕获。

    实际的 HTTP 调用被封装在独立的 ``_post`` 方法中，便于测试时替换（monkeypatch）
    而无需真实联网。
    """

    _ENDPOINT = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        "{model}:generateContent?key={api_key}"
    )

    def __init__(
        self,
        api_key: str,
        model: str = "gemini-2.0-flash",
        timeout: int = 30,
    ) -> None:
        """初始化 Gemini LLM 客户端。

        Args:
            api_key: Google AI Studio 的 API Key（形如 ``AIza...``）。
            model: Gemini 模型名，默认 ``gemini-2.0-flash``。
            timeout: 单次请求的超时时间（秒），默认 30。
        """
        self.api_key = api_key
        self.model = model
        self.timeout = timeout

    def generate(self, prompt: str, **kw) -> str:
        """调用 Gemini ``generateContent`` 端点依据 ``prompt`` 生成文本。

        Args:
            prompt: 提示词文本。
            **kw: 可选生成参数，支持 ``max_tokens``（默认 512）与
                ``temperature``（默认 0.7）。

        Returns:
            模型生成的文本字符串；响应结构缺失或被安全过滤时返回空字符串。

        Raises:
            RuntimeError: 网络错误或 HTTP 4xx/5xx 时抛出，携带状态码与响应体
                前 200 字，交由上层 Agent 捕获。
        """
        url = self._ENDPOINT.format(model=self.model, api_key=self.api_key)
        body = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "maxOutputTokens": kw.get("max_tokens", 2048),
                "temperature": kw.get("temperature", 0.7),
            },
        }
        data = self._post(url, body)
        return self._extract_text(data)

    def _post(self, url: str, body: dict) -> dict:
        """向 ``url`` 发送 JSON POST 并解析返回 JSON（可被测试替换）。

        Args:
            url: 完整的请求地址（已含 ``?key=``）。
            body: 请求体字典，将被序列化为 JSON。

        Returns:
            解析后的响应 JSON 字典。

        Raises:
            RuntimeError: HTTP 4xx/5xx 或网络 / 解析错误时抛出，携带状态码与
                响应体前 200 字。
        """
        payload = json.dumps(body).encode("utf-8")
        request = urllib.request.Request(
            url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as resp:
                raw = resp.read().decode("utf-8")
            return json.loads(raw)
        except urllib.error.HTTPError as exc:
            detail = ""
            try:
                detail = exc.read().decode("utf-8", errors="replace")[:200]
            except Exception:  # noqa: BLE001 - 读取错误体失败时忽略细节
                detail = ""
            raise RuntimeError(
                f"Gemini LLM 调用失败 (model={self.model}, "
                f"status={exc.code}): {detail}"
            ) from exc
        except Exception as exc:  # noqa: BLE001 - 网络 / 解析错误统一上抛
            raise RuntimeError(
                f"Gemini LLM 调用失败 (model={self.model}): {exc}"
            ) from exc

    @staticmethod
    def _extract_text(data: dict) -> str:
        """从 Gemini 响应中提取生成文本，缺失则返回空字符串。

        Args:
            data: ``generateContent`` 的响应 JSON。

        Returns:
            ``candidates[0].content.parts[0].text`` 去除首尾空白后的文本；
            任一层级缺失则返回空字符串。
        """
        try:
            text = data["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError, TypeError):
            return ""
        if not isinstance(text, str):
            return ""
        return text.strip()
