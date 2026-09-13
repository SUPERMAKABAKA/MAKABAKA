"""Clarify_Agent \u65b0\u884c\u4e3a\u5355\u6d4b\uff1a\u54c1\u7c7b\u5207\u6362\u91cd\u7f6e\u3001\u9009\u9879\u751f\u6210\uff08\u89c4\u5219\u5175\u5e95\uff09\u3001ReAct \u5c55\u793a\u6b65\u9aa4\u3002

\u5747\u4f7f\u7528\u65e0 LLM \u6216 MockLLM\uff0c\u4e0d\u6d89\u53ca\u771f\u5b9e\u7f51\u7edc/\u914d\u989d\u3002
"""
from app.agents.clarify_agent import ClarifyAgent
from app.agents.category import detect_category, rule_options, BUDGET_OPTIONS
from app.orchestrator.session import ConversationSession, ChatTurn
from app.orchestrator.models import UserProfile


def _sess(msg):
    s = ConversationSession(session_id="t")
    s.messages.append(ChatTurn(role="user", content=msg))
    return s


def test_detect_category():
    assert detect_category("I want Sony headphones") == "headphones"
    assert detect_category("need a new laptop") == "laptop"
    assert detect_category("hello there") is None


def test_first_turn_no_reset_records_category():
    s = _sess("I want noise cancelling headphones")
    ClarifyAgent().run(s)
    assert s.category == "headphones"
    # \u9996\u8f6e\u4e0d\u7b97\u5207\u6362\uff0c\u4e0d\u4f1a\u56e0\u91cd\u7f6e\u800c\u4e22\u9700\u6c42
    assert s.pending_question is not None


def test_budget_options_present_without_llm():
    s = _sess("I want headphones")
    ClarifyAgent().run(s)
    # \u9996\u4e2a\u7f3a\u5931\u9879\u662f budget\uff0c\u5e94\u7ed9\u51fa\u9884\u7b97\u6863\u4f4d\u9009\u9879
    assert s.clarify_options == list(BUDGET_OPTIONS)
    assert len(s.react_steps) == 1
    assert s.react_steps[0].action


def test_category_switch_resets_needs():
    s = _sess("I want headphones")
    ClarifyAgent().run(s)
    # \u586b\u5165\u9884\u7b97/\u7528\u9014/\u504f\u597d\uff08\u6a21\u62df\u5df2\u6536\u96c6\uff09
    s.collected_needs.budget = 300.0
    s.collected_needs.purpose = "commute"
    s.collected_needs.preferences = ["Sony"]
    # \u540c\u4f1a\u8bdd\u6362\u54c1\u7c7b\uff1alaptop
    s.messages.append(ChatTurn(role="user", content="actually I need a laptop"))
    ClarifyAgent().run(s)
    assert s.category == "laptop"
    # \u91cd\u7f6e\u540e\u9700\u6c42\u88ab\u6e05\u7a7a\uff0c\u91cd\u65b0\u4ece budget \u95ee\u8d77
    assert s.collected_needs.budget is None
    assert s.clarify_options == list(BUDGET_OPTIONS)


def test_preferences_options_by_category():
    # \u76f4\u63a5\u9a8c\u8bc1\u89c4\u5219\u9009\u9879\u6309\u54c1\u7c7b\u53d8\u5316
    assert rule_options("preferences", "headphones") == [
        "Noise cancelling", "Sound quality", "Long battery", "Comfort/portability"]
    assert rule_options("preferences", None) == [
        "Top quality", "Best value", "Popular brand", "Highly rated"]


def test_llm_options_used_then_fallback():
    # LLM \u8fd4\u56de\u5408\u6cd5 JSON \u6570\u7ec4 \u2192 \u91c7\u7528\uff1b\u8fd4\u56de\u5783\u573e \u2192 \u56de\u9000\u89c4\u5219
    class GoodLLM:
        def generate(self, prompt, **kw):
            return '["A budget", "B budget", "C budget", "D budget"]'
    class BadLLM:
        def generate(self, prompt, **kw):
            return "sorry I cannot"
    s1 = _sess("I want headphones")
    ClarifyAgent(GoodLLM()).run(s1)
    assert s1.clarify_options == ["A budget", "B budget", "C budget", "D budget"]
    s2 = _sess("I want headphones")
    ClarifyAgent(BadLLM()).run(s2)
    assert s2.clarify_options == list(BUDGET_OPTIONS)  # \u56de\u9000\u89c4\u5219


def test_profile_autonomous_skips_known_fields():
    # \u6709\u753b\u50cf\uff1abudget/purpose/preferences \u5747\u5df2\u77e5 \u2192 needs_complete \u2192 \u4e0d\u518d\u63d0\u95ee
    s = _sess("I want headphones")
    s.user_profile = UserProfile(user_id="u", preferences=["Sony"], budget=300.0, purpose="commute")
    s.collected_needs.budget = 300.0
    s.collected_needs.purpose = "commute"
    s.collected_needs.preferences = ["Sony"]
    ClarifyAgent().run(s)
    assert s.pending_question is None
    assert s.clarify_options == []
    assert len(s.react_steps) == 1  # \u5c55\u793a\u201c\u9700\u6c42\u5df2\u6e05\u201d\u6b65\u9aa4
