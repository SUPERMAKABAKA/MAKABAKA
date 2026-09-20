"""Property-based tests for shared conversation state behavior."""

from hypothesis import given, settings, strategies as st

from app.agents.clarify_agent import ClarifyAgent
from app.orchestrator.models import UserProfile
from app.orchestrator.session import ChatTurn, CollectedNeeds, ConversationSession


def _count_new_clarify_questions(session: ConversationSession) -> int:
    """Drive one Clarify flow to completion and count questions it creates."""
    agent = ClarifyAgent()
    question_count = 0

    # Guided needs at most three answers; the extra run observes completion.
    for _ in range(4):
        agent.run(session)
        assert session.error is None
        if session.pending_question is None:
            return question_count
        question_count += 1
        question = session.pending_question.lower()
        if "budget" in question:
            answer = "500"
        elif "use" in question:
            answer = "daily use"
        else:
            answer = "quiet comfortable"
        session.messages.append(ChatTurn(role="user", content=answer))

    raise AssertionError("Clarify flow did not complete after all required answers")


@settings(max_examples=100)
@given(
    initial_budget=st.one_of(
        st.none(),
        st.floats(
            min_value=0.01,
            max_value=1_000_000,
            allow_nan=False,
            allow_infinity=False,
        ),
    ),
    initial_purpose=st.one_of(st.none(), st.text(min_size=1, max_size=100)),
    initial_preferences=st.one_of(
        st.none(),
        st.lists(st.text(min_size=1, max_size=50), max_size=10),
    ),
    confirmed_features=st.dictionaries(
        keys=st.sampled_from(("budget", "purpose", "preferences")),
        values=st.booleans(),
        max_size=3,
    ),
    profile_budget=st.one_of(
        st.none(),
        st.floats(
            min_value=0.01,
            max_value=1_000_000,
            allow_nan=False,
            allow_infinity=False,
        ),
    ),
    profile_purpose=st.one_of(st.none(), st.text(min_size=1, max_size=100)),
    profile_preferences=st.lists(st.text(min_size=1, max_size=50), max_size=10),
    pace=st.sampled_from(("direct", "guided")),
)
def test_profiled_session_asks_no_more_new_questions_than_cold_start(
    initial_budget: float | None,
    initial_purpose: str | None,
    initial_preferences: list[str] | None,
    confirmed_features: dict[str, bool],
    profile_budget: float | None,
    profile_purpose: str | None,
    profile_preferences: list[str],
    pace: str,
) -> None:
    """Feature: rag-multi-agent-shopping-assistant, Property 4: 有画像时提问数不增加

    **Validates: Requirements 4.2**
    """
    initial_needs = CollectedNeeds(
        budget=initial_budget,
        purpose=initial_purpose,
        preferences=initial_preferences,
        confirmed_features=confirmed_features,
    )
    cold_session = ConversationSession(
        session_id="property-4-cold-start",
        stage="clarify",
        pace=pace,
        cold_start=True,
        collected_needs=initial_needs.model_copy(deep=True),
    )
    profiled_session = ConversationSession(
        session_id="property-4-profiled",
        stage="clarify",
        pace=pace,
        cold_start=False,
        user_profile=UserProfile(
            user_id="profiled-user",
            budget=profile_budget,
            purpose=profile_purpose,
            preferences=profile_preferences,
        ),
        collected_needs=initial_needs.model_copy(deep=True),
    )

    profiled_questions = _count_new_clarify_questions(profiled_session)
    cold_start_questions = _count_new_clarify_questions(cold_session)

    assert profiled_questions <= cold_start_questions


@settings(max_examples=100)
@given(
    feature=st.sampled_from(("budget", "purpose", "preferences")),
    answer=st.booleans(),
    budget=st.floats(
        min_value=0.01,
        max_value=1_000_000,
        allow_nan=False,
        allow_infinity=False,
    ),
    purpose=st.text(
        alphabet=st.characters(min_codepoint=33, max_codepoint=126),
        min_size=1,
        max_size=100,
    ),
    preferences=st.lists(
        st.text(
            alphabet=st.characters(min_codepoint=33, max_codepoint=126),
            min_size=1,
            max_size=50,
        ),
        min_size=1,
        max_size=10,
    ),
)
def test_yes_no_confirmation_updates_profile_feature_consistently(
    feature: str,
    answer: bool,
    budget: float,
    purpose: str,
    preferences: list[str],
) -> None:
    """Feature: rag-multi-agent-shopping-assistant, Property 5: yes/no 确认更新特征

    **Validates: Requirements 4.3**
    """
    feature_values = {
        "budget": budget,
        "purpose": purpose,
        "preferences": preferences,
    }
    confirm_questions = {
        "budget": f"Your profile suggests a budget around {budget}. Still works? (yes/no)",
        "purpose": f"Your profile shows the use case is {purpose}. Still the case? (yes/no)",
        "preferences": (
            f"Your profile shows you prefer {preferences}. Still a fit? (yes/no)"
        ),
    }
    session = ConversationSession(
        session_id="property-5-yes-no-confirmation",
        stage="clarify",
        user_profile=UserProfile(
            user_id="profiled-user",
            budget=budget,
            purpose=purpose,
            preferences=preferences,
        ),
        collected_needs=CollectedNeeds(
            budget=budget,
            purpose=purpose,
            preferences=preferences,
        ),
        pending_question=confirm_questions[feature],
        messages=[ChatTurn(role="user", content="yes" if answer else "no")],
    )

    result = ClarifyAgent().run(session)

    assert result.error is None
    assert result.collected_needs.confirmed_features[feature] is answer
    expected_value = feature_values[feature] if answer else None
    assert getattr(result.collected_needs, feature) == expected_value


@settings(max_examples=100)
@given(
    budget=st.floats(
        min_value=0.01,
        max_value=1_000_000,
        allow_nan=False,
        allow_infinity=False,
    ),
    purpose=st.text(min_size=1, max_size=100),
    preferences=st.one_of(
        st.none(),
        st.lists(st.text(min_size=1, max_size=50), max_size=10),
    ),
)
def test_direct_pace_advances_when_budget_and_purpose_are_collected(
    budget: float,
    purpose: str,
    preferences: list[str] | None,
) -> None:
    """Feature: rag-multi-agent-shopping-assistant, Property 6: Direct 节奏推进条件

    **Validates: Requirements 4.4**
    """
    session = ConversationSession(
        session_id="property-6-direct-pace",
        pace="direct",
        stage="clarify",
        collected_needs=CollectedNeeds(
            budget=budget,
            purpose=purpose,
            preferences=preferences,
        ),
    )

    # Clarify routing uses needs_complete() to select the retrieval branch.
    assert session.needs_complete() is True


@settings(max_examples=100)
@given(
    user_id=st.text(min_size=1, max_size=64),
    profile_exists=st.booleans(),
)
def test_profile_agent_marks_cold_start_iff_profile_is_missing(
    user_id: str,
    profile_exists: bool,
) -> None:
    """Feature: rag-multi-agent-shopping-assistant, Property 2: 冷启动标记正确性

    **Validates: Requirements 3.2**
    """
    from app.agents.profile_agent import ProfileAgent
    from app.orchestrator.models import UserProfile

    profile = UserProfile(user_id=user_id, preferences=[])

    class MockProfileSource:
        def load(self, requested_user_id: str | None) -> UserProfile | None:
            if profile_exists and requested_user_id == user_id:
                return profile
            return None

    # Begin with the opposite value so both branches must actively set the flag.
    session = ConversationSession(
        session_id="property-2-cold-start",
        user_id=user_id,
        cold_start=profile_exists,
    )

    result = ProfileAgent(MockProfileSource()).run(session)

    assert result.cold_start is (not profile_exists)


@settings(max_examples=100)
@given(
    user_id=st.text(min_size=1, max_size=64),
    preferences=st.lists(st.text(max_size=100), max_size=10),
    budget=st.one_of(
        st.none(),
        st.floats(
            min_value=0.0,
            max_value=1_000_000,
            allow_nan=False,
            allow_infinity=False,
        ),
    ),
    purpose=st.one_of(st.none(), st.text(max_size=100)),
)
def test_profile_agent_maps_loaded_profile_fields_to_session(
    user_id: str,
    preferences: list[str],
    budget: float | None,
    purpose: str | None,
) -> None:
    """Feature: rag-multi-agent-shopping-assistant, Property 3: 画像字段映射

    **Validates: Requirements 3.4**
    """
    from app.agents.profile_agent import ProfileAgent

    profile = UserProfile(
        user_id=user_id,
        preferences=preferences,
        budget=budget,
        purpose=purpose,
    )

    class LoadedProfileSource:
        def load(self, requested_user_id: str | None) -> UserProfile | None:
            assert requested_user_id == profile.user_id
            return profile

    session = ConversationSession(
        session_id="property-3-profile-field-mapping",
        user_id=user_id,
        collected_needs=CollectedNeeds(
            budget=-1.0,
            purpose="stale-purpose",
            preferences=["stale-preference"],
        ),
    )

    result = ProfileAgent(LoadedProfileSource()).run(session)

    assert result.error is None
    assert result.user_profile == profile
    assert result.collected_needs.preferences == profile.preferences
    assert result.collected_needs.budget == profile.budget
    assert result.collected_needs.purpose == profile.purpose


@settings(max_examples=100)
@given(
    product_id=st.from_regex(
        r"[a-z0-9](?:[a-z0-9-]{0,30}[a-z0-9])?",
        fullmatch=True,
    ),
    source_slug=st.from_regex(r"[a-z0-9]{1,32}", fullmatch=True),
    has_detail=st.booleans(),
    texts=st.lists(
        st.text(
            alphabet=st.characters(min_codepoint=33, max_codepoint=126),
            min_size=1,
            max_size=100,
        ),
        min_size=1,
        max_size=6,
    ),
)
def test_ingestion_writes_complete_source_matching_metadata(
    product_id: str,
    source_slug: str,
    has_detail: bool,
    texts: list[str],
) -> None:
    """Feature: rag-multi-agent-shopping-assistant, Property 1: 灌库记录元数据完整

    **Validates: Requirements 1.2, 1.3**
    """
    import logging
    from typing import Any

    from app.interfaces.crawler import CrawledProduct
    from app.rag.ingestion import IngestionPipeline

    source_url = f"https://example.test/products/{source_slug}"
    detail = texts[0] if has_detail else None
    reviews = texts[1:] if has_detail else texts
    product = CrawledProduct(
        product_id=product_id,
        source_url=source_url,
        detail=detail,
        reviews=reviews,
    )

    class SingleProductCrawler:
        def fetch_products(self) -> list[CrawledProduct]:
            return [product]

    class RecordingVectorStore:
        def __init__(self) -> None:
            self.writes: list[tuple[list[float], dict[str, Any]]] = []

        def add(
            self,
            embedding: list[float],
            metadata: dict[str, Any],
        ) -> str:
            self.writes.append((embedding, dict(metadata)))
            return str(len(self.writes))

    store = RecordingVectorStore()
    pipeline = IngestionPipeline(
        crawler=SingleProductCrawler(),  # type: ignore[arg-type]
        store=store,  # type: ignore[arg-type]
        embedder=lambda chunk: [float(len(chunk))],
        logger=logging.getLogger(__name__),
    )

    written = pipeline.run()
    expected_chunks = (
        [texts[0], *texts[1:]] if has_detail else texts
    )

    assert written == len(expected_chunks)
    assert len(store.writes) == len(expected_chunks)
    for (embedding, metadata), chunk in zip(store.writes, expected_chunks):
        assert embedding == [float(len(chunk))]
        assert metadata["product_id"] == product.product_id
        assert metadata["product_id"]
        assert metadata["source_url"] == product.source_url
        assert metadata["source_url"]
        assert metadata["original_text"] == chunk
        assert metadata["original_text"]


@settings(max_examples=100)
@given(
    distances=st.lists(
        st.floats(
            min_value=0.0,
            max_value=1_000_000.0,
            allow_nan=False,
            allow_infinity=False,
        ),
        max_size=30,
    ),
)
def test_retrieval_results_are_sorted_by_non_increasing_relevance(
    distances: list[float],
) -> None:
    """Feature: rag-multi-agent-shopping-assistant, Property 8: 检索结果按相关度排序

    **Validates: Requirements 5.4**
    """
    from app.agents.retrieval_agent import RetrievalAgent
    from app.rag.vector_store import QueryResult

    hits = [
        QueryResult(
            metadata={
                "product_id": f"product-{index}",
                "source_url": f"https://example.test/products/{index}",
                "original_text": f"matched text {index}",
            },
            distance=distance,
        )
        for index, distance in enumerate(distances)
    ]

    class ArbitraryHitStore:
        def query(
            self,
            embedding: list[float],
            top_k: int = 20,
        ) -> list[QueryResult]:
            return hits

    session = ConversationSession(session_id="property-8-relevance-order")
    result = RetrievalAgent(
        store=ArbitraryHitStore(),  # type: ignore[arg-type]
        embedder=lambda _query: [0.0],
    ).run(session)

    assert result.error is None
    scores = [record.relevance_score for record in result.retrieval_results]
    assert all(
        left_score >= right_score
        for left_score, right_score in zip(scores, scores[1:])
    )


@settings(max_examples=100)
@given(
    vector_content=st.lists(
        st.tuples(
            st.from_regex(
                r"[a-z0-9](?:[a-z0-9-]{0,30}[a-z0-9])?",
                fullmatch=True,
            ),
            st.from_regex(r"[a-z0-9]{1,32}", fullmatch=True),
            st.text(
                alphabet=st.characters(min_codepoint=33, max_codepoint=126),
                min_size=1,
                max_size=100,
            ),
            st.floats(
                min_value=0.0,
                max_value=1_000_000.0,
                allow_nan=False,
                allow_infinity=False,
            ),
        ),
        max_size=20,
    ),
    query=st.text(
        alphabet=st.characters(min_codepoint=32, max_codepoint=126),
        max_size=100,
    ),
)
def test_retrieval_results_have_complete_nonempty_fields(
    vector_content: list[tuple[str, str, str, float]],
    query: str,
) -> None:
    """Feature: rag-multi-agent-shopping-assistant, Property 7: 检索结果字段完整

    **Validates: Requirements 5.2**
    """
    from app.agents.retrieval_agent import RetrievalAgent
    from app.rag.vector_store import QueryResult

    hits = [
        QueryResult(
            metadata={
                "product_id": product_id,
                "source_url": f"https://example.test/products/{source_slug}",
                "original_text": matched_text,
            },
            distance=distance,
        )
        for product_id, source_slug, matched_text, distance in vector_content
    ]

    class GeneratedContentStore:
        def query(
            self,
            embedding: list[float],
            top_k: int = 20,
        ) -> list[QueryResult]:
            return hits[:top_k]

    session = ConversationSession(
        session_id="property-7-result-field-completeness",
        collected_needs=CollectedNeeds(purpose=query),
    )
    result = RetrievalAgent(
        store=GeneratedContentStore(),  # type: ignore[arg-type]
        embedder=lambda text: [float(len(text))],
    ).run(session)

    assert result.error is None
    assert len(result.retrieval_results) == len(hits)
    for record in result.retrieval_results:
        assert record.product_id.strip()
        assert record.source_url.strip()
        assert record.matched_text.strip()


@settings(max_examples=100)
@given(
    product_id=st.from_regex(
        r"[a-z0-9](?:[a-z0-9-]{0,30}[a-z0-9])?",
        fullmatch=True,
    ),
    positive_reviews=st.lists(
        st.tuples(
            st.sampled_from(("xiaohongshu", "douyin", "bilibili")),
            st.text(min_size=1, max_size=120),
        ),
        min_size=1,
        max_size=6,
    ),
    negative_reviews=st.lists(
        st.tuples(
            st.sampled_from(("xiaohongshu", "douyin", "bilibili")),
            st.text(min_size=1, max_size=120),
        ),
        min_size=1,
        max_size=6,
    ),
    positive_first=st.booleans(),
)
def test_web_search_aggregation_retains_positive_and_negative_reviews(
    product_id: str,
    positive_reviews: list[tuple[str, str]],
    negative_reviews: list[tuple[str, str]],
    positive_first: bool,
) -> None:
    """Feature: rag-multi-agent-shopping-assistant, Property 9: 测评好评差评覆盖

    **Validates: Requirements 6.3**
    """
    from app.agents.web_search_agent import WebSearchAgent
    from app.interfaces.web_search import WebSearchInterface
    from app.orchestrator.session import RetrievedRecord, SocialReview

    positives = [
        SocialReview(platform=platform, sentiment="positive", content=content)
        for platform, content in positive_reviews
    ]
    negatives = [
        SocialReview(platform=platform, sentiment="negative", content=content)
        for platform, content in negative_reviews
    ]
    candidate_reviews = (
        [*positives, *negatives]
        if positive_first
        else [*negatives, *positives]
    )

    class CandidateReviewSearch(WebSearchInterface):
        def fetch_product_info(self, requested_product_id: str) -> str:
            assert requested_product_id == product_id
            return f"product info for {requested_product_id}"

        def fetch_social_reviews(
            self,
            requested_product_id: str,
        ) -> list[SocialReview]:
            assert requested_product_id == product_id
            return list(candidate_reviews)

    session = ConversationSession(
        session_id="property-9-sentiment-coverage",
        retrieval_results=[
            RetrievedRecord(
                product_id=product_id,
                source_url=f"https://example.test/products/{product_id}",
                matched_text="candidate product",
                relevance_score=1.0,
            )
        ],
    )

    result = WebSearchAgent(CandidateReviewSearch()).run(session)

    assert result.error is None
    assert result.web_status == "ok"
    assert len(result.web_results) == 1
    aggregated_reviews = result.web_results[0].social_reviews
    assert aggregated_reviews == candidate_reviews
    assert {review.sentiment for review in aggregated_reviews} == {
        "positive",
        "negative",
    }
