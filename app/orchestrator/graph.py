"""Orchestrator 条件路由函数 (任务 15.1)。

本模块实现 LangGraph 状态机中各节点完成后的条件路由函数。每个路由函数依据
``ConversationSession`` 的字段决定下一步流向，与 design.md 的
"条件路由函数（体现所有条件边）" 代码严格对齐。

约定：
- 任一 Agent 置 ``session.error`` 时统一路由到 ``"error"`` (Req 8.4)。
- clarify 依 ``needs_complete()`` 决定是继续检索还是让出等待用户 (Req 4.4/4.5)。
- retrieval 的 ``no_match``、web_search 的 ``no_review`` 均不阻断流程 (Req 5.3/6.4)。

图装配 ``build_orchestrator`` 由任务 15.2 追加到本文件。
"""

from __future__ import annotations

from typing import Literal

from app.orchestrator.session import ConversationSession


def route_after_profile(
    s: ConversationSession,
) -> Literal["conversation", "error"]:
    """Profile 完成后进入 conversation（LLM 主导）；失败则 error (Req 8.3/8.4)。"""
    return "error" if s.error else "conversation"


def route_after_conversation(
    s: ConversationSession,
) -> Literal["await_user", "retrieval", "error"]:
    """依 Conversation_Agent 产出的 intent 路由：

    - ``chat``    → 让出等待用户（END），展示自然回复/选项；
    - ``recommend`` → 进入 RAG 检索管线。
    """
    if s.error:
        return "error"
    if s.intent == "recommend":
        return "retrieval"
    return "await_user"


def route_after_retrieval(
    s: ConversationSession,
) -> Literal["web_search", "error"]:
    """检索完成后进入联网测评；no_match 也继续流程 (Req 5.3/8.4)。"""
    return "error" if s.error else "web_search"


def route_after_web_search(
    s: ConversationSession,
) -> Literal["recommendation", "error"]:
    """联网测评完成后进入推荐；no_review 也继续流程 (Req 6.4/8.4)。"""
    return "error" if s.error else "recommendation"


def route_after_recommendation(
    s: ConversationSession,
) -> Literal["done", "error"]:
    """推荐生成完成后结束流程；失败则进入 error (Req 8.3/8.4)。"""
    return "error" if s.error else "done"


# ===========================================================================
# 图装配 build_orchestrator (任务 15.2, Req 8.1/8.2/8.3)
# ---------------------------------------------------------------------------
# 以 ``StateGraph(ConversationSession)`` 注册 5 个 Agent 节点，入口为 profile，
# 用任务 15.1 的路由函数添加所有条件边，最终 ``compile()`` 得到可执行图。
#
# 关于 LangGraph 状态机制：本项目的 Agent 直接在传入的 ``ConversationSession``
# （pydantic BaseModel）上就地更新并返回整个 session。LangGraph 1.x 支持 pydantic
# BaseModel 作为 state schema，且节点返回值可以是「整个 state 对象」或「部分更新
# 的字段字典」。返回整个 session 时，LangGraph 会以其字段覆盖式合并进图状态，从而
# 得到累积后的最终状态。为稳妥地把 Agent 的返回适配为 LangGraph 期望的更新格式，
# 下面用 ``_as_update`` 将节点函数包装为返回「字段字典」，避免不同版本对整对象
# 返回值处理方式的差异，同时保持 Agent 的 run 语义不变（实测 compile 与 invoke
# 均可跑通，见任务验证）。
# ===========================================================================

from dataclasses import dataclass  # noqa: E402

from langgraph.graph import END, StateGraph  # noqa: E402

__all__ = [  # noqa: F822 - 追加导出，前半部分为 15.1 路由函数（模块级隐式可见）
    "AgentBundle",
    "build_orchestrator",
    "build_default_orchestrator",
]


@dataclass
class AgentBundle:
    """持有编排所需的 5 个 Agent 实例 (Req 8.1)。

    字段名与图节点名一一对应（profile/clarify/retrieval/web_search/
    recommendation），``build_orchestrator`` 据此注册节点。每个 Agent 都提供
    ``name`` 属性与 ``run(session) -> session`` 方法。

    Attributes:
        profile: Profile_Agent，加载画像并预填需求。
        conversation: Conversation_Agent，LLM 主导的对话大脑，可暂停节点。
        retrieval: Retrieval_Agent，基于 RAG 的相似度检索。
        web_search: Web_Search_Agent，补充联网信息与社媒测评。
        recommendation: Recommendation_Agent，综合生成推荐列表。
    """

    profile: object
    conversation: object
    retrieval: object
    web_search: object
    recommendation: object


def _as_update(agent):
    """把 Agent 的 ``run`` 适配为 LangGraph 节点函数。

    Agent 就地更新并返回整个 ``ConversationSession``；这里将其转换为返回
    「字段字典」的更新形式，以稳定地与 LangGraph 的 state 合并机制对接
    （无论底层版本如何处理整对象返回值均成立）。

    Args:
        agent: 具备 ``run(session) -> ConversationSession`` 的 Agent 实例。

    Returns:
        签名为 ``(state) -> dict`` 的节点函数，返回值为更新后 session 的字段字典。
    """

    def _node(state: ConversationSession) -> dict:
        updated = agent.run(state)
        # 返回字段字典而非整对象，兼容 LangGraph 的部分更新合并语义。
        return updated.model_dump()

    return _node


def build_orchestrator(agents: AgentBundle):
    """装配并编译多 Agent 编排图 (Req 8.1, 8.2, 8.3)。

    以 ``ConversationSession`` 为共享状态注册 5 个 Agent 节点，入口为 profile，
    再用任务 15.1 的条件路由函数连接所有边：clarify 在需求未收集完时经
    ``await_user`` 让出到 ``END``（可暂停节点），任一 Agent 置 ``error`` 时统一
    经 ``error`` 终止（Req 8.4）。

    Args:
        agents: 持有 5 个 Agent 实例的 ``AgentBundle``。

    Returns:
        编译后的可执行图（``CompiledStateGraph``），可 ``invoke`` 执行整条流程。
    """
    graph = StateGraph(ConversationSession)

    # 节点：每个 Agent 的 run 适配为 (state) -> partial_state_update
    graph.add_node("profile", _as_update(agents.profile))
    graph.add_node("conversation", _as_update(agents.conversation))
    graph.add_node("retrieval", _as_update(agents.retrieval))
    graph.add_node("web_search", _as_update(agents.web_search))
    graph.add_node("recommendation", _as_update(agents.recommendation))

    # 入口：会话进入后固定先执行 profile
    graph.set_entry_point("profile")

    # profile 完成后固定进入 clarify（内部已区分 cold_start / 画像）
    graph.add_conditional_edges(
        "profile",
        route_after_profile,
        {"conversation": "conversation", "error": END},
    )

    # clarify：需求未收集完 -> 让出等待用户（END）；收集完 -> retrieval
    graph.add_conditional_edges(
        "conversation",
        route_after_conversation,
        {"await_user": END, "retrieval": "retrieval", "error": END},
    )

    # retrieval：命中与未命中都继续到 web_search
    graph.add_conditional_edges(
        "retrieval",
        route_after_retrieval,
        {"web_search": "web_search", "error": END},
    )

    # web_search：有无测评都继续到 recommendation
    graph.add_conditional_edges(
        "web_search",
        route_after_web_search,
        {"recommendation": "recommendation", "error": END},
    )

    # recommendation：正常结束或错误终止
    graph.add_conditional_edges(
        "recommendation",
        route_after_recommendation,
        {"done": END, "error": END},
    )

    return graph.compile()


def build_default_orchestrator(container, store, embedder, profile_source, catalog=None):
    """便捷工厂：用 Container 与 RAG 组件装配 5 个 Agent 并编译图。

    从 ``Container`` 取 ``llm()`` / ``web_search()`` 装配 Clarify / Recommendation
    与 Web_Search Agent；用传入的 ``store`` + ``embedder`` 构造 Retrieval_Agent，
    用 ``profile_source`` 构造 Profile_Agent。便于 main.py（任务 16.2）一处装配、
    复用同一编排图。

    Args:
        container: 依赖注入容器（``app.container.Container``），提供 ``llm()``
            与 ``web_search()``。
        store: 向量库封装（``app.rag.vector_store.VectorStore``）。
        embedder: 文本向量化器，契约为 ``embedder(text) -> list[float]``。
        profile_source: 画像源（``ProfileSourceInterface`` 实现）。

    Returns:
        ``(compiled_graph, agent_bundle)`` 二元组：编译后的可执行图与其
        ``AgentBundle``（便于上层复用或检查单个 Agent）。
    """
    # 延迟导入，避免 graph 模块在导入期强耦合具体 Agent 实现。
    from app.agents.clarify_agent import ClarifyAgent
    from app.agents.conversation_agent import ConversationAgent
    from app.agents.profile_agent import ProfileAgent
    from app.agents.recommendation_agent import RecommendationAgent
    from app.agents.retrieval_agent import RetrievalAgent
    from app.agents.web_search_agent import WebSearchAgent

    llm = container.llm()
    web_search = container.web_search()

    bundle = AgentBundle(
        profile=ProfileAgent(profile_source),
        conversation=ConversationAgent(llm, fallback=ClarifyAgent(llm)),
        retrieval=RetrievalAgent(store, embedder),
        web_search=WebSearchAgent(web_search),
        recommendation=RecommendationAgent(llm, catalog=catalog),
    )
    return build_orchestrator(bundle), bundle
