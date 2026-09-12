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
    "budget": "请问您的预算大概是多少？",
    "purpose": "请问您购买这件商品主要用于什么用途？",
    "preferences": "请问您有哪些偏好（如品牌、风格、功能等）？",
}

# 确认现有画像特征时的模板问题（有画像时以确认为主，Req 4.2）。
_CONFIRM_TEMPLATES = {
    "budget": "根据您的画像，预算约为 {value}，还合适吗？（是/否）",
    "purpose": "根据您的画像，用途是「{value}」，仍然如此吗？（是/否）",
    "preferences": "根据您的画像，您偏好「{value}」，这些还符合吗？（是/否）",
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

            # 1) 若存在上一轮待确认特征，且本轮消息是 yes/no，则据此更新（Req 4.3）。
            if session.pending_question is not None and latest is not None:
                self._apply_yes_no(session, latest)

            # 2) 尽量从消息中解析预算数字/用途文本填入 collected_needs（简单解析）。
            if latest is not None:
                self._parse_free_text(session, latest)

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
        """从上一轮问题文本推断其针对的特征键。"""
        if not pending_question:
            return None
        keywords = {
            "budget": ("预算",),
            "purpose": ("用途",),
            "preferences": ("偏好",),
        }
        for feature, words in keywords.items():
            if any(word in pending_question for word in words):
                return feature
        return None

    def _parse_free_text(self, session: ConversationSession, message: str) -> None:
        """从自由文本中简单解析预算数字与用途/偏好文本填入需求。

        规则（简单解析即可）：消息含数字 → 作为 ``budget``；否则非空文本按当前
        缺失的项（用途优先，其次偏好）填入。已确认为 ``False`` 的项优先重新收集。
        """
        needs = session.collected_needs
        text = message.strip()
        if not text:
            return

        # 纯 yes/no 回答不作为自由文本填充，避免污染字段。
        if self._interpret_yes_no(text) is not None and not re.search(r"\d", text):
            return

        number = self._extract_number(text)
        if number is not None and needs.budget is None:
            needs.budget = number
            return

        # 无数字的文本：填入下一个缺失的文本型需求。
        if needs.purpose is None:
            needs.purpose = text
        elif needs.preferences is None:
            needs.preferences = [p for p in re.split(r"[，,、\s]+", text) if p]

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
        """生成缺失项的提问文本，优先借助 LLM，失败回退模板。"""
        template = _QUESTION_TEMPLATES[feature]
        return self._llm_or_template(
            prompt=f"请针对用户的「{feature}」需求，生成一句简短的中文澄清提问。",
            fallback=template,
        )

    def _render_confirm(self, feature: str, value) -> str:
        """生成对既有画像特征的确认提问文本。"""
        template = _CONFIRM_TEMPLATES[feature].format(value=value)
        return self._llm_or_template(
            prompt=(
                f"请生成一句简短的中文确认提问，向用户确认其画像中的「{feature}」"
                f"是否仍为「{value}」。"
            ),
            fallback=template,
        )

    def _llm_or_template(self, prompt: str, fallback: str) -> str:
        """有可用 LLM 时用其生成提问文本，否则/失败时回退到模板。"""
        if self._llm is None:
            return fallback
        try:
            generated = self._llm.generate(prompt)
        except Exception:  # noqa: BLE001 - LLM 不可用时回退，不影响澄清流程
            return fallback
        return generated if generated else fallback
