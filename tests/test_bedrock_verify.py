"""Bedrock 真实实现接入的验证测试。

覆盖：模块可导入、默认配置向后兼容、假 client 下请求构造与响应解析、
环境变量切换实现、mock 端到端 /chat 缺字段 400。均不真实调用 AWS。
"""

from __future__ import annotations

import io
import json

import pytest


def test_modules_import_and_default_backward_compatible():
    """所有模块可导入；默认配置下 llm/embedder 仍为 mock/deterministic。"""
    import app.config  # noqa: F401
    import app.container  # noqa: F401
    import app.interfaces.llm  # noqa: F401
    import app.rag.embedder  # noqa: F401

    from app.config import Settings
    from app.container import Container
    from app.interfaces.llm import MockLLM
    from app.rag.embedder import DeterministicEmbedder

    container = Container(Settings())
    assert isinstance(container.llm(), MockLLM)
    assert isinstance(container.embedder(), DeterministicEmbedder)


class _FakeConverseClient:
    """模拟 bedrock-runtime.converse 的假 client。"""

    def __init__(self):
        self.last_kwargs = None

    def converse(self, **kwargs):
        self.last_kwargs = kwargs
        return {
            "output": {
                "message": {"content": [{"text": "hello from bedrock"}]}
            }
        }


def test_bedrock_llm_request_and_parse():
    """BedrockLLM.generate 请求构造与响应解析正确。"""
    from app.interfaces.llm import BedrockLLM

    fake = _FakeConverseClient()
    llm = BedrockLLM(client=fake)
    out = llm.generate("你好", max_tokens=100, temperature=0.2)

    assert out == "hello from bedrock"
    kw = fake.last_kwargs
    assert kw["modelId"] == "amazon.nova-lite-v1:0"
    assert kw["messages"] == [
        {"role": "user", "content": [{"text": "你好"}]}
    ]
    assert kw["inferenceConfig"] == {"maxTokens": 100, "temperature": 0.2}


def test_bedrock_llm_error_is_wrapped():
    """调用失败被包装为 RuntimeError，不静默吞掉。"""
    from app.interfaces.llm import BedrockLLM

    class _Boom:
        def converse(self, **kwargs):
            raise ValueError("boom")

    llm = BedrockLLM(client=_Boom())
    with pytest.raises(RuntimeError):
        llm.generate("x")


class _FakeInvokeClient:
    """模拟 bedrock-runtime.invoke_model 的假 client。"""

    def __init__(self, vector):
        self.vector = vector
        self.last_kwargs = None

    def invoke_model(self, **kwargs):
        self.last_kwargs = kwargs
        body = json.dumps({"embedding": self.vector})
        return {"body": io.BytesIO(body.encode("utf-8"))}


def test_bedrock_embedder_request_and_parse():
    """BedrockEmbedder.__call__ 请求构造与响应解析正确。"""
    from app.rag.embedder import BedrockEmbedder

    vec = [0.1, 0.2, 0.3]
    fake = _FakeInvokeClient(vec)
    embedder = BedrockEmbedder(dim=3, client=fake)
    out = embedder("测试文本")

    assert out == vec
    kw = fake.last_kwargs
    assert kw["modelId"] == "amazon.titan-embed-text-v2:0"
    sent = json.loads(kw["body"])
    assert sent == {"inputText": "测试文本", "dimensions": 3, "normalize": True}


def test_bedrock_embedder_empty_returns_zero_vector():
    """空文本返回全零向量，不调用 client。"""
    from app.rag.embedder import BedrockEmbedder

    class _NeverCalled:
        def invoke_model(self, **kwargs):  # pragma: no cover
            raise AssertionError("空文本不应调用 client")

    embedder = BedrockEmbedder(dim=5, client=_NeverCalled())
    assert embedder("") == [0.0] * 5
    assert embedder("   ") == [0.0] * 5


def test_env_vars_switch_to_bedrock(monkeypatch):
    """LLM_IMPL/EMBEDDER_IMPL=bedrock 时可装配出 Bedrock 实例。"""
    monkeypatch.setenv("LLM_IMPL", "bedrock")
    monkeypatch.setenv("EMBEDDER_IMPL", "bedrock")

    from app.config import get_settings
    from app.container import Container
    from app.interfaces.llm import BedrockLLM
    from app.rag.embedder import BedrockEmbedder

    settings = get_settings()
    assert settings.llm_impl == "bedrock"
    assert settings.embedder_impl == "bedrock"

    container = Container(settings)
    # boto3.client 不立即校验凭证，实例化应成功。
    assert isinstance(container.llm(), BedrockLLM)
    assert isinstance(container.embedder(), BedrockEmbedder)


def test_chat_missing_fields_returns_400():
    """mock 端到端未被破坏：/chat 缺字段返回 400。"""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.api.routes import router

    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)

    resp = client.post("/chat", json={})
    assert resp.status_code == 400
    assert set(resp.json()["missing_fields"]) == {"session_id", "message"}
