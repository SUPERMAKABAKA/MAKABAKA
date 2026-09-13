"""ConversationAgent tests: LLM-driven chat vs recommend, and quota-failure fallback.

Uses fake in-process LLMs; never touches real Gemini.
"""
import json

from app.agents.conversation_agent import ConversationAgent
from app.agents.clarify_agent import ClarifyAgent
from app.orchestrator.session import ConversationSession, ChatTurn


def _sess(msg):
    s = ConversationSession(session_id="t")
    s.messages.append(ChatTurn(role="user", content=msg))
    return s


class FakeLLM:
    def __init__(self, out):
        self._out = out
    def generate(self, prompt, **kw):
        return self._out


class BoomLLM:
    def generate(self, prompt, **kw):
        raise RuntimeError("429 quota exceeded")


def test_chat_action_natural_reply():
    llm = FakeLLM(json.dumps({"action": "chat", "reply": "Hi! I'm Nova. What are you shopping for?"}))
    s = _sess("who are you")
    ConversationAgent(llm).run(s)
    assert s.intent == "chat"
    assert "Nova" in s.pending_question
    assert s.clarify_options == []


def test_chat_action_with_options():
    llm = FakeLLM(json.dumps({"action": "chat", "reply": "What's your budget?",
                              "options": ["Under $50", "$50-200", "$200+"]}))
    s = _sess("a gift for a cat lover")
    ConversationAgent(llm).run(s)
    assert s.intent == "chat"
    assert s.clarify_options == ["Under $50", "$50-200", "$200+"]


def test_recommend_action_fills_needs_and_triggers_retrieval():
    llm = FakeLLM(json.dumps({"action": "recommend", "query": "cat toys gift",
                              "budget": 40, "purpose": "gift for a cat lover",
                              "preferences": ["fun", "durable"], "count": 3}))
    s = _sess("a gift for a cat lover, around 40 dollars")
    ConversationAgent(llm).run(s)
    assert s.intent == "recommend"
    assert s.pending_question is None
    assert s.collected_needs.budget == 40.0
    assert s.collected_needs.purpose == "gift for a cat lover"
    assert s.collected_needs.preferences == ["fun", "durable"]
    assert s.recommendation_count == 3
    assert len(s.react_steps) == 1


def test_recommend_query_fills_purpose_when_missing():
    llm = FakeLLM(json.dumps({"action": "recommend", "query": "cat toys", "budget": None}))
    s = _sess("cat toys please")
    ConversationAgent(llm).run(s)
    assert s.intent == "recommend"
    assert s.collected_needs.purpose == "cat toys"


def test_llm_failure_degrades_to_clarify():
    # 429 quota -> fall back to deterministic clarify; still functional, intent set.
    s = _sess("I want headphones")
    ConversationAgent(BoomLLM(), fallback=ClarifyAgent()).run(s)
    # clarify records category and asks a question
    assert s.category == "headphones"
    assert s.pending_question is not None
    assert s.intent == "chat"  # needs not complete yet


def test_garbage_llm_output_degrades():
    # MockLLM-style echo (not JSON) -> parse fails -> fallback clarify.
    s = _sess("I want headphones")
    ConversationAgent(FakeLLM("[MockLLM] response to: ..."), fallback=ClarifyAgent()).run(s)
    assert s.pending_question is not None
    assert s.clarify_options  # clarify budget options present


def test_no_llm_uses_fallback():
    s = _sess("I want a laptop")
    ConversationAgent(llm=None, fallback=ClarifyAgent()).run(s)
    assert s.category == "laptop"
    assert s.pending_question is not None
