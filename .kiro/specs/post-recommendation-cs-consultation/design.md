# Design Document

## Overview

本设计在现有购物助手上增加「推荐后按需客服咨询并总结回复」能力。核心流程：一轮推荐成功产出推荐商品后，前端在推荐消息下方展示一组**咨询选择项（Consultation_Offer）**；用户点击「需要咨询」时，前端调用**现有 `/consult` 能力**获得客服回复（Consultation_Transcript），再调用**新增的总结能力**把客服回复提炼成 Consultation_Summary，并作为一条聊天气泡回复到对话流；用户点击「不需要」则安静结束、保留推荐、可继续对话。

设计原则：
- **最小侵入**：不改动 LangGraph 编排图（推荐流程仍在 `recommendation → done` 结束）。咨询与总结发生在推荐**之后**，属于 API/前端层的增量。
- **复用现有**：客服文案继续由 `CustomerService.answer` 生成；总结走现有 `LLMInterface.generate`，无 LLM 时回退规则；数据模型在 `ConsultationResponse` 上最小扩展。
- **不阻断对话**：Consultation_Offer 用现有的“选项按钮”呈现模式，用户也可无视它继续输入。

## Architecture

```
推荐完成 (SSE recommendations 事件, recs 非空)
        │
        ▼
前端渲染推荐 + Consultation_Offer 选项（“需要咨询” / “不需要”）
        │
   ┌────┴─────────────────────────┐
   │需要咨询                        │不需要
   ▼                               ▼
POST /consult/summary            隐藏 Offer，安静结束
(session_id, product_ids?)       保留推荐，可继续对话
   │
   ▼
后端：CustomerService.answer  → Consultation_Transcript
      SummaryService.summarize → Consultation_Summary（LLM 优先，失败回退规则）
   │
   ▼
返回 { reply(=summary), transcript, recommendations }
   │
   ▼
前端：把 summary 作为一条 assistant 聊天气泡渲染到对话流
```

### 关键决策

1. **不入编排图**：咨询是可选的“推荐后动作”，与主编排解耦，避免改动状态机与路由函数，降低回归风险（对应 Req 5）。
2. **新增 `/consult/summary` 端点**而非改造 `/consult`：保持 `/consult`（返回原始客服文案）向后兼容，新端点在其之上叠加总结（对应 Req 5.4）。
3. **总结服务优先 LLM、失败回退规则**：与项目既有约定一致（Req 3.4/5.2/5.3）。规则回退从 Consultation_Transcript 中抽取“结论/优点/注意”要点，不臆造事实（Req 3.5）。
4. **Offer 复用选项按钮呈现**：SSE `recommendations` 事件增加 `consult_offer` 标志；前端据此在推荐消息下渲染两个 chip（Req 1.1、用户已确认方案）。

## Components and Interfaces

### 1. SummaryService（新增）— `app/agents/consultation_summary.py`

```python
class ConsultationSummary:
    def __init__(self, llm: LLMInterface | None = None): ...
    def summarize(
        self,
        transcript: str,
        recommendations: list[ProductRecommendation],
    ) -> str:
        """把客服回复 transcript 提炼为面向用户的简明总结。
        - 有 llm：构造 prompt 调 llm.generate；异常则回退规则。
        - 无 llm / 失败：规则总结（抽取每个商品的结论、主要优点、注意点）。
        """
```

- **LLM 路径**：prompt 要求“仅基于给定客服内容做要点总结，不新增价格/星级/事实；输出简明中文；覆盖推荐倾向、主要优点、需要留意之处”。
- **规则回退**：解析 transcript 中已有的结构（“先说结论/用户认可/需要留意”等行），或退一步基于 `recommendations` 的 `reason` + `summary.positives/negatives` 组织 3~5 行要点。
- **不臆造**（Req 3.5）：回退仅使用 transcript 与 recommendation 已有字段。

### 2. API 层（`app/api/routes.py` + `app/api/models.py`）

**新增请求/响应模型**（models.py）：
```python
class ConsultationSummaryResponse(ConsultationResponse):
    summary: str            # Consultation_Summary（= reply）
    transcript: str         # 原始客服文案（Consultation_Transcript）
```
（沿用 `ConsultationRequest` 作为入参：`session_id` + 可选 `product_ids` + 可选 `message`。）

**新增端点** `POST /consult/summary`（models 兼容，Req 5.4）：
1. 取 `session.recommendations`；为空 → 409（Req 2.3）。
2. 若 `product_ids` 提供，筛选对应商品（Req 2.2）。
3. `transcript = CustomerService.answer(message, selected)`（Req 5.1）。
4. `summary = ConsultationSummary(llm).summarize(transcript, selected)`（Req 3.1）。
5. 返回 `ConsultationSummaryResponse(session_id, reply=summary, summary=summary, transcript=transcript, recommendations=selected)`。

**LLM 装配**：`_Components` 已有 container；新增 `self.llm = container.llm()` 供总结服务使用（无 LLM 环境下 container 返回 MockLLM，规则回退保证不报错，Req 5.3）。

**SSE 事件扩展**：`recommendations` 事件 payload 增加 `"consult_offer": bool(recs)`（Req 1.1/1.2）。

### 3. 前端（`static/index.html`）

- **渲染 Offer**：`recommendations` 事件回来且 `consult_offer` 为真时，在推荐卡片区下方渲染一个 `.consult-offer` 区块，含两个按钮：`需要咨询` / `不需要`。（Req 1.1；无推荐则不渲染，Req 1.2）
- **需要咨询**：点击后按钮进入 loading（Req 2.4），`fetch("/consult/summary", {session_id, product_ids:[本轮全部推荐]})`；成功后用现有 `aiBubble()` 把 `data.reply` 作为一条助手气泡追加到对话流（Req 3.3），并把该 Offer 标记为已处理、隐藏按钮（Req 4.3）。同时右侧客服面板（若打开）可展示原始 transcript（复用现有 `#ppConsult`）。
- **不需要**：隐藏 Offer 区块、不发请求、保留推荐、允许继续输入（Req 4.1/4.2/4.3）。
- **默认全部**：`product_ids` 默认取本轮推荐全部（用户确认方案）。
- **文案**：中文，与现有客服风格一致。

## Data Models

- `ConsultationRequest`（复用，不改）：`session_id`, `message?`, `product_ids?`。
- `ConsultationSummaryResponse`（新增，继承 `ConsultationResponse`）：新增 `summary: str`、`transcript: str`；`reply` 仍为面向用户的总结，保证与前端既有 `data.reply` 读取兼容。
- 会话侧无需新增持久字段；“是否已处理 Offer”由前端按会话内推荐批次维护（避免后端状态膨胀，Req 4.3）。

## Error Handling

| 场景 | 处理 |
|------|------|
| 会话无推荐商品 | `/consult/summary` 返回 409 + ErrorResponse（Req 2.3）；前端提示“需先获取推荐”。|
| `product_ids` 无匹配 | 返回 400 + ErrorResponse。|
| LLM 总结调用异常/超时 | 捕获后回退规则总结，仍返回 200 + 可用 summary（Req 3.4/5.3）。|
| 前端请求失败 | 按钮恢复可点、气泡提示“未生成总结，请重试”。|

## Testing Strategy

- **SummaryService 单测**：
  - 有 MockLLM：`summarize` 返回非空、包含关键要点结构；
  - `llm=None`：走规则回退，返回非空且不含未在输入中出现的臆造价格/星级（Req 3.5）；
  - LLM 抛异常：回退规则、不抛出（Req 3.4）。
- **API 单测**（TestClient）：
  - `/consult/summary` 有推荐 → 200，含 `summary`/`transcript`/`recommendations`，`reply==summary`；
  - 无推荐 → 409；`product_ids` 无匹配 → 400；
  - 指定部分 `product_ids` → 只总结选中的商品（Req 2.2）。
- **SSE 事件**：推荐非空时 `recommendations` 事件含 `consult_offer:true`；无推荐时为 `false`（Req 1.1/1.2）。
- **回归**：现有 `/consult`、`/chat/stream` 测试保持通过；`pytest -q` 全绿。
- **前端**：`Invoke-WebRequest` 校验页面含 Offer 相关元素与处理函数。

## Correctness Properties

以下不变量应在实现与测试中保持（供属性化测试与回归依据）：

### Property 1: 无推荐不咨询
当 `session.recommendations` 为空时，`/consult/summary` 绝不产出 summary，而是返回 409（Req 1.2/2.3）。

**Validates: Requirements 1.2, 2.3**
### Property 2: 总结必有输出
只要存在可咨询推荐，`ConsultationSummary.summarize` 在任意 LLM 可用性下都返回非空字符串（LLM 成功或规则回退），永不抛出未捕获异常（Req 3.1/3.4/5.3）。

**Validates: Requirements 3.1, 3.4, 5.3**
### Property 3: 不臆造事实
规则回退产出的 summary 中出现的价格/星级，必是 transcript 或 recommendation 字段中已有的；不引入新的数值事实（Req 3.5）。

**Validates: Requirements 3.5**
### Property 4: 子集一致性
当传入 `product_ids` 为推荐集合的子集时，参与咨询与总结的商品恰为该子集；空子集（无匹配）返回 400（Req 2.2）。

**Validates: Requirements 2.2**
### Property 5: reply 兼容
`ConsultationSummaryResponse.reply == summary`，保证前端既有 `data.reply` 读取路径不变（Req 5.4）。

**Validates: Requirements 5.4**
### Property 6: 推荐保留
无论用户选择咨询与否，`session.recommendations` 不被本功能修改（Req 4.2）。

**Validates: Requirements 4.2**