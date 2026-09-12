"""内存会话仓（In-Memory Session Repository）。

提供以 ``session_id`` 为键的会话存储抽象。``/chat`` 路由据此按会话标识定位
会话并驱动 Orchestrator（Req 9.2）：首次到达的 ``session_id`` 新建会话，后续
请求复用同一会话对象，从而在多轮对话间保持共享状态（``ConversationSession``）。

本实现将会话保存在进程内的字典中，适用于单进程演示与测试；生产环境可替换为
持久化实现而无需改动调用方。
"""

from __future__ import annotations

from app.orchestrator.session import ConversationSession


class InMemorySessionRepository:
    """基于内存字典的会话仓实现。

    以 ``session.session_id`` 为键在进程内维护会话集合，支持按标识获取或
    新建会话，并在一轮处理完成后回写更新（Req 9.2）。

    Attributes:
        _sessions: 会话标识到 ``ConversationSession`` 的内部映射。
    """

    def __init__(self) -> None:
        """初始化空的会话仓。"""
        self._sessions: dict[str, ConversationSession] = {}

    def get_or_create(self, session_id: str) -> ConversationSession:
        """按标识定位会话，不存在则新建并存入（Req 9.2）。

        Args:
            session_id: 会话标识。

        Returns:
            与 ``session_id`` 对应的会话对象：若已存在返回既有会话，否则新建
            ``ConversationSession(session_id=session_id)`` 存入后返回。
        """
        session = self._sessions.get(session_id)
        if session is None:
            session = ConversationSession(session_id=session_id)
            self._sessions[session_id] = session
        return session

    def save(self, session: ConversationSession) -> None:
        """存储或更新会话，以 ``session.session_id`` 为键（Req 9.2）。

        Args:
            session: 需要持久化的会话对象。同一标识的既有会话将被覆盖为
                传入的最新状态。
        """
        self._sessions[session.session_id] = session
