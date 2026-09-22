"""/consult/summary API 单测与 SSE consult_offer 断言（TestClient）。

覆盖任务 5.2、5.3：
- 有推荐 → 200，含 summary/transcript/recommendations，且 reply == summary；
- 无推荐 → 409；product_ids 无匹配 → 400；子集只总结选中商品（Req 2.2）；
- SSE recommendations 事件：有推荐 consult_offer=true，无推荐为 false（Req 1.1/1.2）。

复用路由模块级 Container/session_repo（默认 mock LLM），不触达真实模型；
通过同一 session_repo 预置带推荐的会话，与路由读取路径保持一致。
"""

import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import routes
from app.orchestrator.models import ProductRecommendation, ReviewSummary


def _rec(product_id: str, title: str) -> ProductRecommendation:
    return ProductRecommendation(
        product_id=product_id,
        title=title,
        reason=f"{title} 与当前需求匹配。",
        product_url=f"https://example.test/dp/{product_id}",
        summary=ReviewSummary(positives=["口碑好", "做工扎实"], negatives=["略贵"]),
        detail=f"{title} 的规格与卖点说明。",
    )


@pytest.fixture()
def client() -> TestClient:
    app = FastAPI()
    app.include_router(routes.router)
    return TestClient(app)


def _seed_session(session_id: str, recommendations: list[ProductRecommendation]) -> None:
    """通过路由使用的同一 session_repo 预置带推荐的会话。"""
    components = routes._get_components()
    session = components.session_repo.get_or_create(session_id)
    session.recommendations = list(recommendations)
    components.session_repo.save(session)


# ---------------------------------------------------------------------------
# 5.2 /consult/summary API 单测
# ---------------------------------------------------------------------------


def test_consult_summary_with_recommendations_returns_200(client: TestClient):
    """有推荐 → 200，含 summary/transcript/recommendations 且 reply == summary。

    Validates: Requirements 2.1, 3.3, 5.4
    """
    sid = "consult-summary-ok"
    recs = [_rec("p1", "耳机A"), _rec("p2", "耳机B")]
    _seed_session(sid, recs)

    resp = client.post("/consult/summary", json={"session_id": sid})
    assert resp.status_code == 200
    body = resp.json()

    assert body["summary"].strip()
    assert body["transcript"].strip()
    assert body["reply"] == body["summary"]
    returned_ids = [r["product_id"] for r in body["recommendations"]]
    assert returned_ids == ["p1", "p2"]


def test_consult_summary_without_recommendations_returns_409(client: TestClient):
    """会话无推荐 → 409（Property 1）。

    Validates: Requirements 2.3
    """
    sid = "consult-summary-empty"
    _seed_session(sid, [])

    resp = client.post("/consult/summary", json={"session_id": sid})
    assert resp.status_code == 409


def test_consult_summary_product_ids_no_match_returns_400(client: TestClient):
    """product_ids 无匹配 → 400（Property 4 空子集）。

    Validates: Requirements 2.2
    """
    sid = "consult-summary-nomatch"
    _seed_session(sid, [_rec("p1", "耳机A")])

    resp = client.post(
        "/consult/summary",
        json={"session_id": sid, "product_ids": ["does-not-exist"]},
    )
    assert resp.status_code == 400


def test_consult_summary_subset_only_summarizes_selected(client: TestClient):
    """product_ids 为子集时，只总结/返回选中的商品（Property 4）。

    Validates: Requirements 2.2
    """
    sid = "consult-summary-subset"
    _seed_session(sid, [_rec("p1", "耳机A"), _rec("p2", "耳机B"), _rec("p3", "耳机C")])

    resp = client.post(
        "/consult/summary",
        json={"session_id": sid, "product_ids": ["p2"]},
    )
    assert resp.status_code == 200
    body = resp.json()
    returned_ids = [r["product_id"] for r in body["recommendations"]]
    assert returned_ids == ["p2"]
    # transcript 只应引用选中的商品，未选中的不应出现。
    assert "耳机B" in body["transcript"]
    assert "耳机A" not in body["transcript"]
    assert "耳机C" not in body["transcript"]


# ---------------------------------------------------------------------------
# 5.3 SSE consult_offer 断言
# ---------------------------------------------------------------------------


def _recommendations_event(raw: str) -> dict:
    """从 SSE 文本中解析 recommendations 事件的 data JSON。"""
    lines = raw.splitlines()
    for index, line in enumerate(lines):
        if line.strip() == "event: recommendations":
            data_line = lines[index + 1]
            assert data_line.startswith("data: ")
            return json.loads(data_line[len("data: "):])
    raise AssertionError("SSE 流中未找到 recommendations 事件")


def test_sse_consult_offer_true_when_recommendations_present(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
):
    """推荐非空时 recommendations 事件含 consult_offer=true。

    Validates: Requirements 1.1
    """
    from app.orchestrator.session import ConversationSession

    recs = [_rec("p1", "耳机A")]

    def fake_run_turn(body, authorization):
        result = ConversationSession(session_id=body.get("session_id", "s"))
        result.recommendations = recs
        result.recommendation_status = "ok"
        result.pending_question = "这里是为你精选的推荐。"
        return result, None

    monkeypatch.setattr(routes, "_run_turn", fake_run_turn)

    resp = client.post(
        "/chat/stream", json={"session_id": "sse-with-recs", "message": "推荐耳机"}
    )
    assert resp.status_code == 200
    payload = _recommendations_event(resp.text)
    assert payload["consult_offer"] is True


def test_sse_consult_offer_false_when_no_recommendations(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
):
    """无推荐时 recommendations 事件 consult_offer 为 false。

    Validates: Requirements 1.2
    """
    from app.orchestrator.session import ConversationSession

    def fake_run_turn(body, authorization):
        result = ConversationSession(session_id=body.get("session_id", "s"))
        result.recommendations = []
        result.pending_question = "再多告诉我一点你的需求吧。"
        return result, None

    monkeypatch.setattr(routes, "_run_turn", fake_run_turn)

    resp = client.post(
        "/chat/stream", json={"session_id": "sse-no-recs", "message": "你好"}
    )
    assert resp.status_code == 200
    payload = _recommendations_event(resp.text)
    assert payload["consult_offer"] is False
