"""Profile_Agent：加载并解析模拟画像 (Req 3.1, 3.2, 3.4, 8.2)。

按 design.md 的 Agent 输入/输出契约，Profile_Agent 读取 ``session.user_id``，
经模拟画像源加载画像：

- 命中画像 → 写入 ``session.user_profile``，并将画像的偏好/预算/用途预填至
  ``session.collected_needs``（Req 3.1, 3.4）。
- 未命中或未提供 ``user_id`` → 标记 ``session.cold_start = True``（Req 3.2）。
- 捕获到不可恢复错误 → 设置 ``session.error = AgentError(agent="profile", ...)``
  供 Orchestrator 据此终止（Req 8.4）。

Profile_Agent 仅经 ``ProfileSourceInterface`` 访问外部画像数据，符合“外部依赖
只经接口访问”的约束。
"""

from __future__ import annotations

from app.orchestrator.session import AgentError, ConversationSession
from app.repositories.profile_source import ProfileSourceInterface

__all__ = ["ProfileAgent"]


class ProfileAgent:
    """加载并解析模拟画像，预填需求或标记冷启动 (Req 3.1, 3.2, 3.4)。"""

    name = "profile"

    def __init__(self, profile_source: ProfileSourceInterface) -> None:
        """初始化 Profile_Agent。

        Args:
            profile_source: 画像源抽象；仅依赖接口类型，便于替换实现
                （Req 2.4）。
        """
        self._profile_source = profile_source

    def run(self, session: ConversationSession) -> ConversationSession:
        """加载画像并更新会话状态 (Req 3.1, 3.2, 3.4, 8.2)。

        Args:
            session: 共享会话状态，读取 ``user_id``。

        Returns:
            更新后的 ``ConversationSession``：命中画像时写入 ``user_profile``
            并预填 ``collected_needs``；未命中时置 ``cold_start=True``；异常时
            置 ``error``。
        """
        try:
            profile = self._profile_source.load(session.user_id)
        except Exception as exc:  # noqa: BLE001 - 不可恢复错误统一传播 (Req 8.4)
            session.error = AgentError(
                agent=self.name,
                message=f"加载用户画像失败：{exc}",
            )
            return session

        if profile is None:
            # 未命中或未提供 user_id：标记冷启动 (Req 3.2)
            session.cold_start = True
            return session

        # 命中画像：写入画像并预填偏好/预算/用途 (Req 3.1, 3.4)
        session.user_profile = profile
        session.cold_start = False
        session.collected_needs.preferences = list(profile.preferences)
        session.collected_needs.budget = profile.budget
        session.collected_needs.purpose = profile.purpose
        return session
