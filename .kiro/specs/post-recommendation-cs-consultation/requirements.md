# Requirements Document

## Introduction

本特性在现有购物助手基础上扩展一个「推荐后按需客服咨询并总结回复」的能力。当推荐生成完成后，系统不再默默结束，而是**显式询问用户是否需要与推荐商品的（模拟）客服进一步咨询**。若用户选择「需要」，系统会基于当前推荐商品运行一次客服咨询对话，然后把这段客服咨询的内容**总结**后作为一条助手消息回复给用户；若用户选择「不需要」，则正常结束本轮，不做多余动作。

本特性复用现有基础设施：`/consult` 接口、`CustomerService` 客服回复生成、`ConsultationRequest`/`ConsultationResponse` 数据模型，以及前端已有的推荐渲染与客服面板。新增部分集中在：推荐完成后的「是否咨询」选择项、按需触发客服咨询的编排、以及对客服咨询内容做二次总结再回复。

## Glossary

- **Assistant_System**: 智能购物助手系统整体。
- **Recommendation_Result**: 一次推荐流程产出的推荐商品列表（`session.recommendations`）。
- **Consultation_Offer**: 推荐完成后向用户呈现的「是否需要与客服进一步咨询」选择项。
- **Customer_Service**: 现有的模拟客服能力（`CustomerService.answer`），基于推荐商品的详情与评论生成客服风格回复。
- **Consultation_Transcript**: 一次客服咨询产生的原始客服回复内容。
- **Consultation_Summary**: 对 Consultation_Transcript 做二次提炼后、面向用户的简明总结回复。
- **Summary_Service**: 负责把 Consultation_Transcript 总结为 Consultation_Summary 的能力（优先 LLM，失败回退规则）。
- **Conversation_Session**: 对话会话，保存推荐结果与本轮咨询相关状态。
- **Opt_In**: 用户在 Consultation_Offer 中选择「需要咨询」。
- **Opt_Out**: 用户在 Consultation_Offer 中选择「不需要咨询」。

## Requirements

### Requirement 1: 推荐后主动询问是否咨询

**User Story:** As a 购物用户, I want 在拿到推荐商品后系统主动问我要不要进一步咨询客服, so that 我可以自主决定是否深入了解而不被强制打扰

#### Acceptance Criteria

1. WHEN 一轮推荐流程成功产出至少一个推荐商品, THE Assistant_System SHALL 在推荐结果之后呈现一个 Consultation_Offer，包含「需要咨询」与「不需要」两个明确选项。
2. IF 一轮推荐流程未产出任何推荐商品, THEN THE Assistant_System SHALL 不呈现 Consultation_Offer。
3. THE Consultation_Offer SHALL 以不阻断对话的方式呈现，用户可以选择其一，也可以直接继续输入其他消息。
4. WHILE 用户尚未对 Consultation_Offer 做出选择, THE Assistant_System SHALL 不自动发起客服咨询。

### Requirement 2: 按需自动完成一轮客服咨询

**User Story:** As a 购物用户, I want 选择「需要咨询」后系统自动与推荐商品的客服完成一轮咨询, so that 我无需自己逐条追问就能获得客服视角的解读

#### Acceptance Criteria

1. WHEN 用户在 Consultation_Offer 中选择 Opt_In, THE Assistant_System SHALL 基于当前 Recommendation_Result 运行一次 Customer_Service 咨询并得到 Consultation_Transcript。
2. WHERE 用户仅针对部分推荐商品发起咨询, THE Assistant_System SHALL 只就被选中的推荐商品运行咨询。
3. IF 当前会话没有可供咨询的推荐商品, THEN THE Assistant_System SHALL 返回一条说明「需先获取推荐」的提示且不发起咨询。
4. WHILE 客服咨询正在进行, THE Assistant_System SHALL 向用户呈现进行中的状态提示。

### Requirement 3: 客服咨询内容总结后回复

**User Story:** As a 购物用户, I want 系统把客服咨询的内容总结后再回复我, so that 我能快速抓住重点而不必读完整段客服原文

#### Acceptance Criteria

1. WHEN Customer_Service 咨询产出 Consultation_Transcript, THE Summary_Service SHALL 将其提炼为一段面向用户的 Consultation_Summary。
2. THE Consultation_Summary SHALL 覆盖被咨询商品的关键结论（如推荐倾向、主要优点、需要留意之处），并保持简明。
3. THE Assistant_System SHALL 将 Consultation_Summary 作为一条助手消息回复给用户。
4. IF Summary_Service 的 LLM 总结调用失败, THEN THE Assistant_System SHALL 回退到基于规则的总结，且仍返回一条可用的 Consultation_Summary。
5. THE Summary_Service SHALL 不臆造 Consultation_Transcript 中不存在的价格、星级或事实性信息。

### Requirement 4: 选择不咨询时安静结束

**User Story:** As a 购物用户, I want 选择「不需要」时系统安静结束本轮, so that 我不想咨询时不会被打扰

#### Acceptance Criteria

1. WHEN 用户在 Consultation_Offer 中选择 Opt_Out, THE Assistant_System SHALL 不发起客服咨询，并结束本轮咨询提示。
2. WHEN 用户选择 Opt_Out 后, THE Assistant_System SHALL 保留推荐结果并允许用户继续正常对话。
3. THE Consultation_Offer SHALL 在用户完成一次选择后不再重复要求对同一批推荐做选择。

### Requirement 5: 复用现有客服与接口约定

**User Story:** As a 开发者, I want 该功能复用现有客服与接口约定, so that 改动最小且与既有编排一致

#### Acceptance Criteria

1. THE Assistant_System SHALL 复用现有 `/consult` 能力与 `CustomerService` 生成 Consultation_Transcript，而非新引入并行的客服实现。
2. THE Summary_Service SHALL 通过现有 LLM 接口抽象调用大模型，并遵循「失败回退规则」的既有约定。
3. WHEN 后端在无 LLM 可用的环境运行, THE Assistant_System SHALL 仍能通过规则回退产出 Consultation_Summary 而不报错。
4. THE 新增接口/字段 SHALL 与现有 `ConsultationRequest`/`ConsultationResponse` 数据模型保持兼容或以最小方式扩展。