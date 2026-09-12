"""Clarify_Agent：多轮澄清，收集/确认用户购物需求 (Req 4.1–4.6)。

Clarify_Agent 对有画像与无画像的会话使用**同一 run 例程**，仅靠提问轮次调节
交互深度（Req 4.6）：

- 冷启动（无画像）时对缺失的预算/用途/偏好逐项提问（Req 4.1）；
- 有画像时以确认现有画像特征为主、跳过已知项，从而减少新增提问（Req 4.2）；
- 用户对某特征给出 yes/no 时，直接更新 ``confirmed_features`` 与对应字段
  （Req 4.3）；
- Guided 节奏逐项分轮提问（Req 4.5），Direct 节奏在预算+用途就绪即推进
  （由 ``needs_complete()`` 封装差异，Req 4.4/4.5）。

Clarify_Agent 是**可暂停节点**：仍有缺失项时把下一个问题写入
``session.pending_question`` 并让出，等待下一次请求携带用户回答后从此处恢复；
需求收集完成后将 ``pending_question`` 置 ``None``。

外部依赖只经接口访问：本 Agent 可选依赖 ``LLMInterface`` 生成更自然的提问文本，
未注入或调用失败时回退到确定性模板问题，保证离线可用。
"""

from __future__ import annotations

import re
from typing import Optional

from app.interfaces.llm import LLMInterface
from app.orchestrator.session import AgentError, ConversationSession

__all__ = ["ClarifyAgent"]

# 待收集/确认的需求特征键。顺序即 Guided 节奏下的逐项提问顺序（Req 4.5）。
_FEATURES = ("budget", "purpose", "preferences")

# 各特征的确定性模板问题（LLM 不可用时回退，保证离线可用）。
_QUESTION_TEMPLATES = {
    "budget": "What is your rough budget for this?",
    "purpose": "What will you mainly use it for?",
    "preferences": "Any preferences on brand, style or key features?",
}

# 确认现有画像特征时的模板问题（有画像时以确认为主，Req 4.2）。
_CONFIRM_TEMPLATES = {
    "budget": "Your profile suggests a budget around {value}. Still works? (yes/no)",
    "purpose": "Your profile shows the use case is {value}. Still the case? (yes/no)",
    "preferences": "Your profile shows you prefer {value}. Still a fit? (yes/no)",
}

# yes/no 识别词表（大小写不敏感）。
_YES_WORDS = ("yes", "y", "是", "对", "好", "好的", "可以", "没错", "correct", "sure")
_NO_WORDS = ("no", "n", "否", "不", "不是", "不对", "不用", "不行", "错")


class ClarifyAgent:
    """需求澄清 Agent，实现有画像/冷启动统一澄清流程 (Req 4.1–4.6)。

    Attributes:
        name: Agent 标识，用于错误传播时标注失败来源（Req 8.4）。
    """

    name = "clarify"

    def __init__(self, llm: Optional[LLMInterface] = None) -> None:
        """初始化澄清 Agent。

        Args:
            llm: 可选的 LLM 接口，用于生成更自然的提问文本；未注入时使用
                确定性模板问题（Req 2.1）。
        """
        self._llm = llm

    def run(self, session: ConversationSession) -> ConversationSession:
        """执行一轮澄清：解析用户回答、更新需求、必要时产出下一个问题。

        Args:
            session: 共享会话状态。

        Returns:
            更新 ``collected_needs``（含 ``confirmed_features``）与
            ``pending_question`` 后的会话；出错时设置 ``session.error``。
        """
        try:
            latest = self._latest_user_message(session)

            # 记住上一轮正在问的字段（pending-field 驱动本轮回答的路由）。
            # 首轮时 pending_question 为 None，active 亦为 None。
            active = self._pending_feature(session.pending_question)
            confirming = self._is_confirm_question(session.pending_question)

            if latest is not None:
                # 1) 上一轮是「确认既有画像值」且本轮为 yes/no：走 yes/no 更新（Req 4.3）。
                if active is not None and confirming \
                        and self._interpret_yes_no(latest) is not None:
                    self._apply_yes_no(session, latest)
                else:
                    # 2) 否则按「上一轮正在问哪个字段」路由用户这轮回答。
                    self._route_answer(session, active, latest)

            # 3) 有画像时用画像已有值预填，减少提问（Req 4.2）。
            self._prefill_from_profile(session)

            # 4) 判定是否收集完：完成则清空 pending_question，否则产出下一个问题。
            if session.needs_complete():
                session.pending_question = None
            else:
                session.pending_question = self._next_question(session)

            return session
        except Exception as exc:  # noqa: BLE001 - 统一转为可传播的 AgentError（Req 8.4）
            session.error = AgentError(agent=self.name, message=str(exc))
            return session

    # ---- 消息解析 ----

    @staticmethod
    def _latest_user_message(session: ConversationSession) -> Optional[str]:
        """返回最近一条用户消息的内容，无则返回 ``None``。"""
        for turn in reversed(session.messages):
            if turn.role == "user":
                return turn.content
        return None

    def _apply_yes_no(self, session: ConversationSession, message: str) -> None:
        """将 yes/no 回答映射到上一轮待确认特征（Req 4.3）。

        识别问题针对的特征后，把 ``confirmed_features[feature]`` 置为
        ``True``/``False``；确认为 ``False`` 时清空对应字段以便后续重新收集。
        """
        answer = self._interpret_yes_no(message)
        if answer is None:
            return
        feature = self._pending_feature(session.pending_question)
        if feature is None:
            return

        needs = session.collected_needs
        needs.confirmed_features[feature] = answer
        if answer is False:
            # 用户否定既有特征：清空对应字段，等待重新提供（Req 4.3）。
            setattr(needs, feature, None)

    @staticmethod
    def _interpret_yes_no(message: str) -> Optional[bool]:
        """将消息解释为 yes/no；无法判定时返回 ``None``。"""
        text = message.strip().lower()
        if not text:
            return None
        # 否定优先，避免「不好」被误判为肯定。
        for word in _NO_WORDS:
            if word in text:
                return False
        for word in _YES_WORDS:
            if word in text:
                return True
        return None

    @staticmethod
    def _pending_feature(pending_question: Optional[str]) -> Optional[str]:
        """从上一轮问题文本推断其针对的特征键。

        直接比对英文问题/确认模板文案而非猜关键词，保证与实际问题模板一致：
        - 普通提问模板做等值/包含匹配；
        - 确认模板含 ``{value}`` 格式化后的变体，故用 ``{value}`` 之前的固定
          前缀做前缀匹配。

        返回 ``"budget"`` / ``"purpose"`` / ``"preferences"`` 或 ``None``。
        """
        if not pending_question:
            return None
        text = pending_question.strip()

        # 普通提问模板：等值或包含匹配。
        for feature, template in _QUESTION_TEMPLATES.items():
            if text == template or template in text:
                return feature

        # 确认模板：用 {value} 之前的固定前缀做前缀匹配。
        for feature, template in _CONFIRM_TEMPLATES.items():
            prefix = template.split("{value}", 1)[0]
            if prefix and text.startswith(prefix):
                return feature
        return None

    @staticmethod
    def _is_confirm_question(pending_question: Optional[str]) -> bool:
        """判定上一轮问题是否为「确认既有画像值」的确认型提问。"""
        if not pending_question:
            return False
        text = pending_question.strip()
        for template in _CONFIRM_TEMPLATES.values():
            prefix = template.split("{value}", 1)[0]
            if prefix and text.startswith(prefix):
                return True
        return False

    def _route_answer(
        self,
        session: ConversationSession,
        active: Optional[str],
        message: str,
    ) -> None:
        """基于「上一轮正在问哪个字段」把本轮回答路由到对应字段。

        - ``active == "budget"``：从消息提取数字填 ``budget``；无数字则保留旧值。
        - ``active == "purpose"``：整句（去空白）填 ``purpose``。
        - ``active == "preferences"``：按分隔符切分填 ``preferences`` 列表。
        - ``active is None``（首轮自由描述）：智能首填——含数字则填 ``budget``，
          并把整句作为 ``purpose`` 候选（``purpose`` 为空时填入）。

        以 ``active`` 字段为准，避免同一轮把一个回答错配到多个字段导致跳字段。
        """
        needs = session.collected_needs
        text = message.strip()
        if not text:
            return

        if active == "budget":
            number = self._extract_number(text)
            if number is not None:
                needs.budget = number
            return

        if active == "purpose":
            needs.purpose = text
            return

        if active == "preferences":
            prefs = self._split_preferences(text)
            if prefs:
                needs.preferences = prefs
            return

        # 首轮（active is None）：智能首填。
        number = self._extract_number(text)
        if number is not None and needs.budget is None:
            needs.budget = number
        if needs.purpose is None:
            needs.purpose = text

    @staticmethod
    def _split_preferences(text: str) -> list[str]:
        """按英文逗号、中文逗号、顿号、空白切分偏好文本为列表。"""
        return [p for p in re.split(r"[，,、\s]+", text) if p]

    @staticmethod
    def _extract_number(text: str) -> Optional[float]:
        """从文本中提取第一个数字作为预算，失败返回 ``None``。"""
        match = re.search(r"\d+(?:\.\d+)?", text.replace(",", ""))
        if match is None:
            return None
        try:
            return float(match.group())
        except ValueError:
            return None

    # ---- 画像预填 ----

    @staticmethod
    def _prefill_from_profile(session: ConversationSession) -> None:
        """用画像已有值预填缺失需求，减少新增提问（Req 4.2）。

        仅在字段缺失且未被用户显式否定（``confirmed_features`` 为 ``False``）时
        预填，避免覆盖用户当轮的回答或否定结果。
        """
        profile = session.user_profile
        if profile is None:
            return
        needs = session.collected_needs
        for feature in _FEATURES:
            if needs.confirmed_features.get(feature) is False:
                continue
            if getattr(needs, feature, None) is not None:
                continue
            profile_value = getattr(profile, feature, None)
            if profile_value is not None:
                setattr(needs, feature, profile_value)

    # ---- 提问生成 ----

    def _next_question(self, session: ConversationSession) -> str:
        """产出下一个待澄清问题（Req 4.1/4.5）。

        Guided 节奏按 ``_FEATURES`` 顺序取第一个缺失项逐项提问；有画像且该项
        已有值待确认时，以确认口吻提问（Req 4.2）。
        """
        needs = session.collected_needs
        for feature in self._missing_features(session):
            profile_value = self._profile_value(session, feature)
            if profile_value is not None and needs.confirmed_features.get(feature) is None:
                # 有画像值但尚未确认：以确认为主减少提问（Req 4.2）。
                return self._render_confirm(feature, profile_value)
            return self._render_question(feature)
        # 理论上 needs_complete() 为 False 时必有缺失项；兜底返回通用提问。
        return _QUESTION_TEMPLATES["preferences"]

    def _missing_features(self, session: ConversationSession) -> list[str]:
        """按 Direct/Guided 差异返回仍需收集的特征列表（Req 4.4/4.5）。"""
        needs = session.collected_needs
        required = _FEATURES if session.pace != "direct" else ("budget", "purpose")
        return [f for f in required if getattr(needs, f, None) is None]

    @staticmethod
    def _profile_value(session: ConversationSession, feature: str):
        """返回画像中对应特征的值，无画像/无值时返回 ``None``。"""
        profile = session.user_profile
        if profile is None:
            return None
        return getattr(profile, feature, None)

    def _render_question(self, feature: str) -> str:
        """Return the deterministic English template question for a missing field.

        Clarification prompts are a key product interaction, so we use fixed,
        controllable copy instead of live LLM generation. This keeps the
        language consistent (English UI), the wording stable, and never leaks
        internal prompt text. The LLM is reserved for recommendation reasons.
        """
        return _QUESTION_TEMPLATES[feature]

    def _render_confirm(self, feature: str, value) -> str:
        """Return the deterministic English confirmation question for a profile field."""
        return _CONFIRM_TEMPLATES[feature].format(value=value)
