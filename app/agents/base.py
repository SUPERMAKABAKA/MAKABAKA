"""Agent 协议定义 (Req 8.2)。

所有专职子 Agent 遵循统一契约：拥有标识 ``name``，并实现 ``run`` 接收共享状态
``ConversationSession`` 且返回更新后的同类型对象。Agent 之间不直接调用彼此，只
通过 ``ConversationSession`` 交换数据，流转由 Orchestrator 的条件边决定。

采用 ``typing.Protocol`` 定义结构化契约：任何具备 ``name`` 属性与匹配签名
``run`` 方法的类都视为满足 ``Agent``，无需显式继承，便于依赖注入与替换实现。
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.orchestrator.session import ConversationSession

__all__ = ["Agent"]


@runtime_checkable
class Agent(Protocol):
    """专职子 Agent 的统一协议 (Req 8.2)。

    Attributes:
        name: Agent 标识，用于错误传播时标注失败来源 (Req 8.4)。
    """

    name: str

    def run(self, session: ConversationSession) -> ConversationSession:
        """执行本 Agent 的职责并返回更新后的会话状态。

        Args:
            session: 在所有 Agent 间传递的唯一共享状态。

        Returns:
            仅追加/更新本 Agent 负责字段后的 ``ConversationSession``。
        """
        ...
