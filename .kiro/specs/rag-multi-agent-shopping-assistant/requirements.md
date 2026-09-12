# Requirements Document

## Introduction

本特性在现有 FastAPI 项目基础上扩展一个基于 RAG 与多 Agent 编排的智能购物助手。系统通过一个编排器（Orchestrator）协调 5 个专职子 Agent（用户画像 Agent、需求澄清 Agent、检索 Agent、联网搜索 Agent、推荐生成 Agent），基于 LangGraph 状态机进行对话流程编排。系统将预爬取的亚马逊商品评论与详情灌入本地 Chroma 向量库作为检索基础，结合联网搜索与社交媒体测评信息，通过多轮对话澄清用户需求，最终输出带有推荐理由、商品链接与评论总结的商品推荐列表。

所有外部依赖（爬虫、联网搜索、社交媒体测评抓取、LLM 调用）均通过接口抽象与模拟实现提供，保证可插拔与可替换。用户画像数据在本阶段以模拟数据形式提供。

## Glossary

- **Assistant_System**: 智能购物助手系统整体，承载多 Agent 编排、对话与推荐能力。
- **Orchestrator**: 编排器，基于 LangGraph 状态机驱动子 Agent 之间的流转与状态传递。
- **Profile_Agent**: 用户画像 Agent，负责加载并解析模拟用户画像数据。
- **Clarify_Agent**: 需求澄清 Agent，负责通过多轮提问收集与确认用户购物需求。
- **Retrieval_Agent**: 检索 Agent，负责基于 RAG 从 Chroma 向量库检索相关商品评论与详情。
- **Web_Search_Agent**: 联网搜索 Agent，负责获取商品信息及社交媒体测评内容。
- **Recommendation_Agent**: 推荐生成 Agent，负责综合信息生成最终推荐列表与输出内容。
- **Vector_Store**: 本地 Chroma 向量库，存储商品评论与详情的向量化表示。
- **Ingestion_Pipeline**: 数据采集与灌库流程，将预爬取的商品数据处理并写入 Vector_Store。
- **Crawler_Interface**: 爬虫接口抽象，定义商品评论与详情的获取契约。
- **Web_Search_Interface**: 联网搜索接口抽象，定义商品信息与社交媒体测评的获取契约。
- **LLM_Interface**: 大语言模型接口抽象，定义文本生成与推理调用契约。
- **User_Profile**: 用户画像，包含用户偏好、历史、预算等模拟属性的数据结构。
- **Conversation_Session**: 对话会话，保存单次交互中的对话状态、已收集需求与 Agent 中间结果。
- **Product_Recommendation**: 单个商品推荐条目，包含推荐理由、商品链接与评论总结。
- **Cold_Start**: 冷启动场景，指当前用户无可用画像的情形。
- **Pace_Direct**: 直接推荐节奏，指以较少提问快速产出推荐的对话策略。
- **Pace_Guided**: 逐步引导节奏，指以较多提问逐步收敛需求的对话策略。

## Requirements

### Requirement 1

**User Story:** As a 系统运维人员, I want 将预爬取的亚马逊商品评论与详情灌入向量库, so that RAG 检索具备可用的数据基础

#### Acceptance Criteria

1. THE Ingestion_Pipeline SHALL 通过 Crawler_Interface 读取约 50 种亚马逊商品的评论与详情数据。
2. WHEN Ingestion_Pipeline 处理一条商品数据, THE Ingestion_Pipeline SHALL 将该商品的详情与评论文本转换为向量表示并写入 Vector_Store。
3. THE Ingestion_Pipeline SHALL 为每条写入 Vector_Store 的记录保留商品标识、来源链接与原始文本作为元数据。
4. IF 一条商品数据缺少详情或评论字段, THEN THE Ingestion_Pipeline SHALL 跳过该字段并记录一条包含商品标识的处理日志。
5. WHERE Crawler_Interface 使用模拟实现, THE Crawler_Interface SHALL 返回预置的商品评论与详情数据。

### Requirement 2

**User Story:** As a 开发者, I want 外部依赖通过接口抽象与模拟实现提供, so that 系统组件可插拔且可替换

#### Acceptance Criteria

1. THE Assistant_System SHALL 通过 Crawler_Interface、Web_Search_Interface 与 LLM_Interface 访问所有外部依赖。
2. THE Assistant_System SHALL 为 Crawler_Interface、Web_Search_Interface 与 LLM_Interface 各提供一个模拟实现。
3. WHERE 配置指定某接口使用模拟实现, THE Assistant_System SHALL 在启动时装配该接口的模拟实现。
4. WHEN 某接口的实现被替换为另一个符合同一接口契约的实现, THE Assistant_System SHALL 在不修改调用方代码的情况下使用新实现。

### Requirement 3

**User Story:** As a 购物用户, I want 系统加载我的用户画像, so that 推荐能结合我的已知偏好

#### Acceptance Criteria

1. WHEN 一个 Conversation_Session 开始, THE Profile_Agent SHALL 尝试为当前用户加载 User_Profile。
2. IF 当前用户不存在可用的 User_Profile, THEN THE Profile_Agent SHALL 将当前会话标记为 Cold_Start。
3. THE Profile_Agent SHALL 从模拟数据源加载 User_Profile。
4. WHEN Profile_Agent 加载到 User_Profile, THE Profile_Agent SHALL 将画像中的偏好、预算与用途字段写入 Conversation_Session。

### Requirement 4

**User Story:** As a 购物用户, I want 系统通过多轮对话澄清我的需求, so that 推荐更贴合我的真实意图

#### Acceptance Criteria

1. WHILE 一个 Conversation_Session 处于 Cold_Start, THE Clarify_Agent SHALL 就预算、用途与偏好逐项向用户提问。
2. WHILE 一个 Conversation_Session 已加载 User_Profile, THE Clarify_Agent SHALL 以确认现有画像特征为主减少新增提问数量。
3. WHEN 用户对某画像特征给出 yes 或 no 的确认响应, THE Clarify_Agent SHALL 依据该响应更新 Conversation_Session 中的对应特征。
4. WHERE 用户选择 Pace_Direct 节奏, THE Clarify_Agent SHALL 在收集到预算与用途后进入推荐流程。
5. WHERE 用户选择 Pace_Guided 节奏, THE Clarify_Agent SHALL 就预算、用途与偏好分多轮逐步提问。
6. THE Clarify_Agent SHALL 对有画像与无画像的会话使用同一对话流程并通过提问轮次调节交互深度。

### Requirement 5

**User Story:** As a 购物用户, I want 系统从向量库检索相关商品信息, so that 推荐基于真实的商品评论与详情

#### Acceptance Criteria

1. WHEN Conversation_Session 中的需求收集完成, THE Retrieval_Agent SHALL 依据已收集的需求从 Vector_Store 检索相关商品记录。
2. THE Retrieval_Agent SHALL 为每条检索结果返回商品标识、来源链接与匹配的评论或详情文本。
3. IF Vector_Store 未返回任何匹配记录, THEN THE Retrieval_Agent SHALL 向 Orchestrator 返回空结果并附带无匹配的状态标识。
4. THE Retrieval_Agent SHALL 按相关度对检索结果排序。

### Requirement 6

**User Story:** As a 购物用户, I want 系统联网获取商品信息与社交媒体测评, so that 推荐融合外部真实反馈

#### Acceptance Criteria

1. WHEN Orchestrator 触发外部信息补充, THE Web_Search_Agent SHALL 通过 Web_Search_Interface 获取候选商品的商品信息。
2. THE Web_Search_Agent SHALL 通过 Web_Search_Interface 获取来自小红书、抖音与 B 站的社交媒体测评内容。
3. THE Web_Search_Agent SHALL 同时收集好评与差评类型的测评内容。
4. IF Web_Search_Interface 未返回任何测评内容, THEN THE Web_Search_Agent SHALL 向 Orchestrator 返回空结果并附带无测评的状态标识。
5. WHERE Web_Search_Interface 使用模拟实现, THE Web_Search_Interface SHALL 返回预置的商品信息与社交媒体测评数据。

### Requirement 7

**User Story:** As a 购物用户, I want 系统生成带理由与总结的商品推荐, so that 我能快速判断是否选择该商品

#### Acceptance Criteria

1. WHEN Retrieval_Agent 与 Web_Search_Agent 的结果就绪, THE Recommendation_Agent SHALL 生成一个 Product_Recommendation 列表。
2. THE Recommendation_Agent SHALL 默认在推荐列表中包含 3 至 5 个 Product_Recommendation。
3. WHERE 用户指定了推荐数量, THE Recommendation_Agent SHALL 按用户指定的数量生成 Product_Recommendation。
4. THE Recommendation_Agent SHALL 为每个 Product_Recommendation 包含推荐理由、商品链接与基于评论及测评的总结。
5. THE Recommendation_Agent SHALL 在每个 Product_Recommendation 的总结中体现好评与差评两方面内容。
6. IF 可用候选商品数量少于目标推荐数量, THEN THE Recommendation_Agent SHALL 返回全部可用候选商品并附带数量不足的状态标识。

### Requirement 8

**User Story:** As a 编排设计者, I want Orchestrator 基于状态机协调各子 Agent, so that 对话流程可控且各 Agent 职责清晰

#### Acceptance Criteria

1. THE Orchestrator SHALL 基于 LangGraph 状态机在 Profile_Agent、Clarify_Agent、Retrieval_Agent、Web_Search_Agent 与 Recommendation_Agent 之间流转。
2. THE Orchestrator SHALL 在各子 Agent 之间通过 Conversation_Session 传递状态与中间结果。
3. WHEN 一个子 Agent 完成处理, THE Orchestrator SHALL 依据状态机定义流转至下一个子 Agent。
4. IF 某个子 Agent 返回错误状态, THEN THE Orchestrator SHALL 终止当前流程并向调用方返回包含失败 Agent 标识的错误响应。

### Requirement 9

**User Story:** As a 前端或客户端开发者, I want 通过 API 接口与购物助手交互, so that 我能集成对话与推荐能力

#### Acceptance Criteria

1. THE Assistant_System SHALL 提供一个接收用户消息并返回助手响应的对话 API 接口。
2. WHEN 对话 API 接口收到一条包含会话标识与用户消息的请求, THE Assistant_System SHALL 在对应的 Conversation_Session 上驱动 Orchestrator 并返回助手响应。
3. WHEN 推荐流程完成, THE Assistant_System SHALL 在 API 响应中返回 Product_Recommendation 列表。
4. IF 对话 API 请求缺少会话标识或用户消息, THEN THE Assistant_System SHALL 返回一条包含缺失字段名称的错误响应。
5. WHERE 请求指定了推荐数量参数, THE Assistant_System SHALL 将该数量传递给 Recommendation_Agent。
