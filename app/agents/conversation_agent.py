"""Conversation_Agent: LLM-driven conversation brain (replaces the hard-coded clarify flow).

Nova is a friendly assistant that can chat naturally AND has professional shopping
skills. Each turn we hand the conversation history + profile to the LLM, which decides:
  * "chat"      -> a natural reply (chit-chat, clarifying, guiding), optional pickable options
  * "recommend" -> enough info gathered; provide a search query + needs, triggering RAG.

RAG shopping is a TOOL the LLM invokes, not a fixed pipeline. The LLM is the brain.

Degradation: with no LLM / call failure / parse failure / quota exhausted, fall back to
the deterministic clarify (reusing ClarifyAgent) so the service does not stall when the
Gemini quota runs out.
"""

from __future__ import annotations

import json
import re
from typing import Optional

from app.interfaces.llm import LLMInterface
from app.orchestrator.session import (
    AgentError,
    ConversationSession,
    ReactStep,
)

__all__ = ["ConversationAgent"]


_SYSTEM_PROMPT = """You are Nova, a friendly and professional shopping assistant.
You can chat naturally about anything, but your specialty is helping people find \
products. You have access to a product catalog with reviews (a RAG tool) that you \
can invoke when you know enough to recommend.

On every turn, decide what to do and reply with ONLY a single JSON object, no \
markdown, no code fences, using one of these two shapes:

1) When you want to talk, greet, answer a question, or ask the shopper for more \
detail before recommending:
{"action":"chat","reply":"<your natural reply>","options":["<opt1>","<opt2>"]}
- "options" is OPTIONAL: include 2-5 short clickable choices ONLY when you are \
asking the shopper to pick something (e.g. budget ranges or key features). Omit \
"options" for normal chit-chat.

2) When you have enough to search the catalog and recommend products:
{"action":"recommend","query":"<concise search query>","budget":<number or null>,\
"purpose":"<what they will use it for or null>","preferences":["<pref1>",...],\
"count":<number or null>}
- Use "recommend" as soon as you reasonably understand what they want. Do not \
over-interrogate. For a clear request like "a gift for a cat lover" you may either \
ask ONE clarifying question (chat) or go straight to recommend.

Rules:
- Keep replies concise and warm.
- Never output anything except the single JSON object.
- Language: reply in the shopper language.
"""


class ConversationAgent:
    """LLM-driven conversation agent; falls back to deterministic clarify on failure."""

    name = "conversation"

    def __init__(
        self,
        llm: Optional[LLMInterface] = None,
        fallback: Optional[object] = None,
    ) -> None:
        """Init.

        Args:
            llm: LLM interface; when None, go straight to fallback clarify.
            fallback: deterministic clarify agent (has run(session)), usually ClarifyAgent.
        """
        self._llm = llm
        self._fallback = fallback

    def run(self, session: ConversationSession) -> ConversationSession:
        """Run one conversation turn, setting session.intent to 'chat' or 'recommend'."""
        try:
            latest = self._latest_user_message(session)

            decision = None
            if self._llm is not None and latest is not None:
                decision = self._decide(session)

            if decision is None:
                # Degrade: no LLM / parse failure / quota exhausted -> deterministic clarify.
                return self._run_fallback(session)

            action = decision.get("action")
            if action == "recommend":
                self._apply_recommend(session, decision)
                session.pending_question = None
                session.clarify_options = []
                session.intent = "recommend"
                session.react_steps = [ReactStep(
                    thought="I understand what the shopper needs.",
                    plan="Search the product catalog and summarize real reviews.",
                    action="Generating recommendations.",
                )]
            else:
                # Default / unknown action treated as chat.
                reply = str(decision.get("reply") or "").strip()
                if not reply:
                    return self._run_fallback(session)
                session.pending_question = reply
                opts = decision.get("options")
                session.clarify_options = (
                    [str(o).strip() for o in opts if str(o).strip()]
                    if isinstance(opts, list) else []
                )
                session.intent = "chat"
                session.react_steps = []
            return session
        except Exception as exc:  # noqa: BLE001 - propagate as AgentError (Req 8.4)
            session.error = AgentError(agent=self.name, message=str(exc))
            return session

    # ---- LLM decision ----

    def _decide(self, session: ConversationSession) -> Optional[dict]:
        """Call the LLM for a structured decision; return None on failure/parse-miss."""
        prompt = self._build_prompt(session)
        try:
            raw = self._llm.generate(prompt)
        except Exception:  # noqa: BLE001 - call failure (incl. 429 quota) -> degrade
            return None
        return self._parse_decision(raw)

    def _build_prompt(self, session: ConversationSession) -> str:
        """Assemble system prompt + profile summary + conversation history."""
        lines = [_SYSTEM_PROMPT, ""]
        profile = session.user_profile
        if profile is not None:
            parts = []
            if profile.budget is not None:
                parts.append(f"budget~{profile.budget}")
            if profile.purpose:
                parts.append(f"usual use: {profile.purpose}")
            if profile.preferences:
                parts.append("prefers: " + ", ".join(profile.preferences))
            if parts:
                lines.append("Known shopper profile (use it, do not re-ask what you "
                             "already know): " + "; ".join(parts))
                lines.append("")
        lines.append("Conversation so far:")
        for turn in session.messages[-12:]:
            who = "Shopper" if turn.role == "user" else "Nova"
            lines.append(f"{who}: {turn.content}")
        lines.append("")
        lines.append("Respond with the single JSON object now.")
        return "\n".join(lines)

    @staticmethod
    def _parse_decision(text: Optional[str]) -> Optional[dict]:
        """Parse a JSON object from LLM output; tolerate code fences and stray text."""
        if not text:
            return None
        cleaned = text.strip()
        fence = re.match(r"^```[a-zA-Z]*\s*(.*?)\s*```$", cleaned, re.DOTALL)
        if fence:
            cleaned = fence.group(1).strip()
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start == -1 or end == -1 or end <= start:
            return None
        try:
            obj = json.loads(cleaned[start:end + 1])
        except (ValueError, TypeError):
            return None
        if not isinstance(obj, dict) or "action" not in obj:
            return None
        return obj

    @staticmethod
    def _apply_recommend(session: ConversationSession, decision: dict) -> None:
        """Write LLM-extracted needs into collected_needs for retrieval to use."""
        needs = session.collected_needs
        budget = decision.get("budget")
        if isinstance(budget, (int, float)) and not isinstance(budget, bool):
            needs.budget = float(budget)
        purpose = decision.get("purpose")
        query = decision.get("query")
        # If purpose missing, use query so the retrieval query is non-empty.
        if isinstance(purpose, str) and purpose.strip():
            needs.purpose = purpose.strip()
        elif isinstance(query, str) and query.strip():
            needs.purpose = query.strip()
        prefs = decision.get("preferences")
        if isinstance(prefs, list):
            cleaned = [str(p).strip() for p in prefs if str(p).strip()]
            if cleaned:
                needs.preferences = cleaned
        count = decision.get("count")
        if isinstance(count, int) and not isinstance(count, bool) and count > 0:
            session.recommendation_count = count

    # ---- degradation ----

    def _run_fallback(self, session: ConversationSession) -> ConversationSession:
        """Degrade to deterministic clarify (no LLM or LLM unavailable)."""
        if self._fallback is not None:
            result = self._fallback.run(session)
            result.intent = "recommend" if result.needs_complete() else "chat"
            return result
        # No fallback and no LLM: push straight to recommend to avoid a dead loop.
        session.intent = "recommend"
        session.pending_question = None
        return session

    @staticmethod
    def _latest_user_message(session: ConversationSession) -> Optional[str]:
        for turn in reversed(session.messages):
            if turn.role == "user":
                return turn.content
        return None
