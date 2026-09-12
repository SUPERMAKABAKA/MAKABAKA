# Implementation Plan: RAG 多 Agent 购物助手

## Overview

按依赖顺序增量实现：先搭建项目结构与共享数据模型，再实现接口抽象层与模拟实现及依赖注入容器，随后构建 RAG 层（向量库/embedder/灌库流程）与预置数据集，接着逐个实现 5 个 Agent，再用 LangGraph 编排状态机与条件路由，之后接入会话仓、画像源与 FastAPI `/chat` 路由，最后补齐 18 条属性测试与单元/边界测试。每步都基于前一步产物，最终在 `main.py` 与路由处完成整体接线。语言：Python（设计已确定）。

## Tasks

- [x] 1. 项目结构、依赖与配置
  - 创建 `app/`、`data/`、`scripts/`、`tests/` 目录及各子包 `__init__.py`（`app/api`、`app/orchestrator`、`app/agents`、`app/interfaces`、`app/rag`、`app/repositories`）
  - 在 `requirements.txt` 增补 `langgraph`、`chromadb`、`pydantic`，测试依赖 `pytest`、`hypothesis`
  - 创建 `app/config.py` 定义 `Settings`（crawler/web_search/llm 实现选择、chroma_dir、数据集路径）
  - _Requirements: 2.3_

- [x] 2. 共享状态与核心数据模型
  - [x] 2.1 实现 ConversationSession 及其子模型
    - 在 `app/orchestrator/session.py` 实现 `CollectedNeeds`、`RetrievedRecord`、`SocialReview`、`WebInfo`、`ChatTurn`、`AgentError`、`ConversationSession`
    - 实现 `ConversationSession.needs_complete()`（Direct 需预算+用途；Guided 需预算+用途+偏好）
    - _Requirements: 4.4, 4.5, 8.2_
  - [x] 2.2 实现输出与画像数据模型
    - 在 `app/orchestrator/session.py`（或 `app/api/models.py`）实现 `ReviewSummary`、`ProductRecommendation`、`UserProfile`
    - _Requirements: 3.4, 7.4, 7.5_
  - [ ]* 2.3 编写 needs_complete 属性测试
    - **Property 6: Direct 节奏推进条件**
    - **Validates: Requirements 4.4**

- [x] 3. 接口抽象层与模拟实现
  - [x] 3.1 定义 Crawler 接口与模拟实现
    - 在 `app/interfaces/crawler.py` 实现 `CrawledProduct`、`CrawlerInterface`、`MockCrawler`（从 `products.json` 读取约 50 种预置商品）
    - _Requirements: 1.1, 1.5, 2.1, 2.2_
  - [x] 3.2 定义 WebSearch 接口与模拟实现
    - 在 `app/interfaces/web_search.py` 实现 `WebSearchInterface`、`MockWebSearch`（`fetch_product_info`、`fetch_social_reviews` 从 `web_reviews.json` 返回小红书/抖音/B站好评与差评）
    - _Requirements: 6.1, 6.2, 6.3, 6.5, 2.1, 2.2_
  - [x] 3.3 定义 LLM 接口与模拟实现
    - 在 `app/interfaces/llm.py` 实现 `LLMInterface`、`MockLLM`（基于模板的确定性输出）
    - _Requirements: 2.1, 2.2_
  - [ ]* 3.4 编写接口模拟实现单元测试
    - 验证三个模拟实现返回预置数据；验证 WebSearch 覆盖三平台来源
    - _Requirements: 1.5, 2.2, 6.2, 6.5_

- [x] 4. 依赖注入容器
  - [x] 4.1 实现 Container 装配逻辑
    - 在 `app/container.py` 实现 `Container`，按 `Settings` 选择 `crawler()`/`web_search()`/`llm()` 的模拟实现，调用方仅依赖抽象类型
    - _Requirements: 2.3, 2.4_
  - [ ]* 4.2 编写容器装配与可替换性单元测试
    - 验证按配置装配模拟实现；验证替换为符合同一契约的实现不改调用方
    - _Requirements: 2.3, 2.4_

- [x] 5. 预置数据集
  - 创建 `data/products.json`（约 50 种商品，含 product_id、source_url、detail、reviews，含少量缺字段样本）
  - 创建 `data/web_reviews.json`（各商品的 product_info 与含好评/差评的社媒测评）
  - 创建 `data/profiles.json`（若干模拟 UserProfile，覆盖有画像与冷启动场景）
  - _Requirements: 1.5, 6.5, 3.3_

- [ ] 6. RAG 层：向量库、embedder 与灌库
  - [x] 6.1 实现 embedder 与 VectorStore 封装
    - 在 `app/rag/embedder.py` 实现确定性 embedding（离线可测）
    - 在 `app/rag/vector_store.py` 封装 Chroma，提供 `add(embedding, metadata)` 与 `query(embedding, top_k)`（返回含 metadata 与 distance）
    - _Requirements: 1.2, 5.1_
  - [~] 6.2 实现 IngestionPipeline
    - 在 `app/rag/ingestion.py` 实现 `IngestionPipeline.run()`：读取商品→字段校验（缺 detail/reviews 跳过并记录含 product_id 日志）→切分→向量化→写入 Chroma（metadata 含 product_id/source_url/original_text）
    - _Requirements: 1.1, 1.2, 1.3, 1.4_
  - [ ]* 6.3 编写灌库元数据完整性属性测试
    - **Property 1: 灌库记录元数据完整**
    - **Validates: Requirements 1.2, 1.3**
  - [ ]* 6.4 编写缺字段跳过与日志边界测试
    - 验证缺 detail/reviews 时跳过该字段并记录含 product_id 的日志
    - _Requirements: 1.4_
  - [~] 6.5 实现灌库脚本
    - 在 `scripts/ingest.py` 通过 Container 装配 crawler/store/embedder 并运行 IngestionPipeline
    - _Requirements: 1.1_

- [~] 7. Checkpoint - 确保数据层与接口层测试通过
  - Ensure all tests pass, ask the user if questions arise.

- [x] 8. 会话仓与画像源
  - [x] 8.1 实现内存会话仓
    - 在 `app/repositories/session_repo.py` 实现 `get_or_create(session_id)` 与 `save(session)`
    - _Requirements: 9.2_
  - [x] 8.2 实现模拟画像源
    - 在 `app/repositories/profile_source.py` 从 `profiles.json` 按 user_id 加载 `UserProfile`，无画像返回 None
    - _Requirements: 3.3_

- [ ] 9. Profile Agent
  - [~] 9.1 实现 Profile_Agent
    - 在 `app/agents/base.py` 定义 `Agent` 协议；在 `app/agents/profile_agent.py` 实现 `run`：加载画像→写入偏好/预算/用途；无画像标记 cold_start；异常置 `session.error`
    - _Requirements: 3.1, 3.2, 3.4, 8.2_
  - [ ]* 9.2 编写冷启动标记属性测试
    - **Property 2: 冷启动标记正确性**
    - **Validates: Requirements 3.2**
  - [ ]* 9.3 编写画像字段映射属性测试
    - **Property 3: 画像字段映射**
    - **Validates: Requirements 3.4**

- [ ] 10. Clarify Agent
  - [~] 10.1 实现 Clarify_Agent
    - 在 `app/agents/clarify_agent.py` 实现统一流程：冷启动对缺失预算/用途/偏好逐项提问；有画像以确认现有特征为主减少提问；yes/no 回答更新 `confirmed_features` 与对应字段；未收集完置 `pending_question`
    - _Requirements: 4.1, 4.2, 4.3, 4.5, 4.6_
  - [ ]* 10.2 编写有画像提问数不增加属性测试
    - **Property 4: 有画像时提问数不增加**
    - **Validates: Requirements 4.2**
  - [ ]* 10.3 编写 yes/no 确认更新属性测试
    - **Property 5: yes/no 确认更新特征**
    - **Validates: Requirements 4.3**

- [ ] 11. Retrieval Agent
  - [~] 11.1 实现 Retrieval_Agent
    - 在 `app/agents/retrieval_agent.py` 实现 `run`：由 `collected_needs` 构造查询→向量化→Chroma 检索→映射为 `RetrievedRecord`（product_id/source_url/matched_text）→按相关度降序排序；空结果置 `retrieval_status="no_match"`
    - _Requirements: 5.1, 5.2, 5.3, 5.4_
  - [ ]* 11.2 编写检索结果字段完整属性测试
    - **Property 7: 检索结果字段完整**
    - **Validates: Requirements 5.2**
  - [ ]* 11.3 编写检索结果排序属性测试
    - **Property 8: 检索结果按相关度排序**
    - **Validates: Requirements 5.4**
  - [ ]* 11.4 编写检索空结果边界测试
    - 验证无匹配时返回空列表并置 `retrieval_status="no_match"`
    - _Requirements: 5.3_

- [ ] 12. Web Search Agent
  - [~] 12.1 实现 Web_Search_Agent
    - 在 `app/agents/web_search_agent.py` 实现 `run`：对候选商品经 `Web_Search_Interface` 获取 product_info 与社媒测评（好评+差评），聚合为 `web_results`；无测评置 `web_status="no_review"`
    - _Requirements: 6.1, 6.2, 6.3, 6.4_
  - [ ]* 12.2 编写测评好评差评覆盖属性测试
    - **Property 9: 测评好评差评覆盖**
    - **Validates: Requirements 6.3**
  - [ ]* 12.3 编写无测评边界测试
    - 验证无测评时置 `web_status="no_review"` 并继续流程
    - _Requirements: 6.4_

- [ ] 13. Recommendation Agent
  - [~] 13.1 实现 Recommendation_Agent
    - 在 `app/agents/recommendation_agent.py` 实现 `run`：融合 `retrieval_results` 与 `web_results` 生成 `ProductRecommendation`（reason/product_url/含好评差评的 summary）；默认 3–5 条；指定数量按数量输出；候选不足置 `recommendation_status="insufficient"`
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6_
  - [ ]* 13.2 编写默认推荐数量区间属性测试
    - **Property 10: 默认推荐数量区间**
    - **Validates: Requirements 7.2**
  - [ ]* 13.3 编写指定数量精确输出属性测试
    - **Property 11: 指定数量精确输出**
    - **Validates: Requirements 7.3**
  - [ ]* 13.4 编写推荐条目字段完整属性测试
    - **Property 12: 推荐条目字段完整**
    - **Validates: Requirements 7.4**
  - [ ]* 13.5 编写总结好评差评属性测试
    - **Property 13: 总结体现好评与差评**
    - **Validates: Requirements 7.5**
  - [ ]* 13.6 编写候选不足边界测试
    - 验证候选少于目标数量时返回全部并置 `recommendation_status="insufficient"`
    - _Requirements: 7.6_

- [~] 14. Checkpoint - 确保各 Agent 测试通过
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 15. Orchestrator LangGraph 状态机
  - [~] 15.1 实现路由函数
    - 在 `app/orchestrator/graph.py` 实现 `route_after_profile`、`route_after_clarify`（await_user/retrieval/error）、`route_after_retrieval`、`route_after_web_search`、`route_after_recommendation`
    - _Requirements: 8.3, 8.4, 4.4, 4.5, 5.3, 6.4_
  - [~] 15.2 实现 build_orchestrator 图装配
    - 在 `app/orchestrator/graph.py` 用 `StateGraph(ConversationSession)` 注册 5 节点、设入口、添加条件边并 `compile()`
    - _Requirements: 8.1, 8.2, 8.3_
  - [ ]* 15.3 编写会话状态单调累积属性测试
    - **Property 14: 会话状态单调累积**
    - **Validates: Requirements 8.2**
  - [ ]* 15.4 编写错误传播属性测试
    - **Property 15: 错误传播携带失败 Agent 标识**
    - **Validates: Requirements 8.4**
  - [ ]* 15.5 编写图结构与路由单元测试
    - 验证图含 5 节点与预期边；验证节点完成后的路由
    - _Requirements: 8.1, 8.3_

- [ ] 16. FastAPI /chat 接口
  - [~] 16.1 实现请求/响应模型
    - 在 `app/api/models.py` 实现 `ChatRequest`（含 recommendation_count）、`ChatResponse`、`ErrorResponse`
    - _Requirements: 9.1, 9.4, 9.5_
  - [~] 16.2 实现 /chat 路由并接线到 main.py
    - 在 `app/api/routes.py` 实现 `/chat`：缺字段→400+missing_fields；按 session_id 定位会话；透传 recommendation_count；驱动 orchestrator；错误→500+failed_agent；完成返回推荐列表
    - 在 `main.py` 装配 Container、会话仓、orchestrator 并挂载路由
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5, 8.4_
  - [ ]* 16.3 编写会话路由一致性属性测试
    - **Property 16: 会话路由一致性**
    - **Validates: Requirements 9.2**
  - [ ]* 16.4 编写缺字段错误命名属性测试
    - **Property 17: 缺字段错误命名**
    - **Validates: Requirements 9.4**
  - [ ]* 16.5 编写推荐数量透传属性测试
    - **Property 18: 推荐数量透传**
    - **Validates: Requirements 9.5**
  - [ ]* 16.6 编写 /chat 端到端单元测试
    - 验证基本可用与推荐完成时返回推荐列表
    - _Requirements: 9.1, 9.3_

- [~] 17. Final checkpoint - 确保全部测试通过
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- 标记 `*` 的子任务为可选（单元/属性/边界测试），可为快速 MVP 跳过
- 每个任务关联具体需求编号，便于追溯
- Checkpoint 用于增量验证
- 18 条属性测试使用 Hypothesis，每条至少 100 次迭代，标签格式 `Feature: rag-multi-agent-shopping-assistant, Property {n}: {text}`，就近放置于对应实现之后
- Agent 之间仅通过 ConversationSession 交换数据，流转由 Orchestrator 条件边决定

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["2.1", "2.2", "3.1", "3.2", "3.3", "5"] },
    { "id": 1, "tasks": ["2.3", "3.4", "4.1", "6.1", "8.1", "8.2"] },
    { "id": 2, "tasks": ["4.2", "6.2", "6.5", "9.1", "10.1", "11.1", "12.1", "13.1", "16.1"] },
    { "id": 3, "tasks": ["6.3", "6.4", "9.2", "9.3", "10.2", "10.3", "11.2", "11.3", "11.4", "12.2", "12.3", "13.2", "13.3", "13.4", "13.5", "13.6", "15.1"] },
    { "id": 4, "tasks": ["15.2"] },
    { "id": 5, "tasks": ["15.3", "15.4", "15.5", "16.2"] },
    { "id": 6, "tasks": ["16.3", "16.4", "16.5", "16.6"] }
  ]
}
```
