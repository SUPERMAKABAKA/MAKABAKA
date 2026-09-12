"""LLM 接口抽象与模拟实现。

本模块定义大语言模型的接口契约 (``LLMInterface``) 以及一个基于模板的
确定性模拟实现 (``MockLLM``)。模拟实现对相同输入始终产生相同输出，便于
离线测试与可复现的编排流程。

相关需求：2.1（外部依赖经接口访问）、2.2（每个接口提供模拟实现）。
"""

from __future__ import annotations

import hashlib
from abc import ABC, abstractmethod

__all__ = ["LLMInterface", "MockLLM"]


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
