"""RetrievalAgent 空检索结果的边界单元测试。"""

from app.agents.retrieval_agent import RetrievalAgent
from app.orchestrator.graph import route_after_retrieval
from app.orchestrator.session import (
    CollectedNeeds,
    ConversationSession,
    RetrievedRecord,
)
from app.rag.embedder import DeterministicEmbedder
from app.rag.vector_store import VectorStore


def test_empty_vector_store_returns_no_match_without_agent_error() -> None:
    """空向量库返回空结果和 no_match，而不是不可恢复的 Agent 错误。

    Validates: Requirements 5.3
    """
    session = ConversationSession(
        session_id="empty-retrieval",
        collected_needs=CollectedNeeds(
            budget=100.0,
            purpose="日常使用",
            preferences=["轻便"],
        ),
        retrieval_results=[
            RetrievedRecord(
                product_id="stale-product",
                source_url="https://example.com/stale-product",
                matched_text="上一次检索遗留的结果",
                relevance_score=1.0,
            )
        ],
    )
    agent = RetrievalAgent(VectorStore(), DeterministicEmbedder())

    result = agent.run(session)

    assert result.retrieval_results == []
    assert result.retrieval_status == "no_match"
    assert result.error is None


def test_no_match_routes_to_web_search_so_flow_can_continue() -> None:
    """no_match 是可继续状态，检索后仍路由到 web_search。

    Validates: Requirements 5.3
    """
    session = ConversationSession(
        session_id="no-match-routing",
        retrieval_results=[],
        retrieval_status="no_match",
    )

    assert session.error is None
    assert route_after_retrieval(session) == "web_search"
