# Implementation Plan

## Overview

在现有购物助手上增量实现「推荐后按需客服咨询并总结回复」。后端新增总结服务与 `/consult/summary` 端点，复用现有 `CustomerService` 与 `LLMInterface`（失败回退规则）；SSE 推荐事件增加 `consult_offer` 标志；前端在推荐后渲染咨询选择项，选择「需要咨询」时调用端点并把总结作为聊天气泡回复。不改动 LangGraph 编排图。

## Task Dependency Graph

```
1 (SummaryService) ─┐
2 (Models) ─────────┼─> 3 (/consult/summary + LLM 装配) ─> 5.1, 5.2
                    │
4 (SSE consult_offer) ─────────────────────────────────> 5.3
3, 4 ──────────────────────> 6 (前端) ──> 7 (验证与回归)
5.1, 5.2, 5.3 ─────────────────────────────────────────> 7
```

- 任务 1、2、4 可并行起步；3 依赖 1、2；6 依赖 3、4；5.x 依赖各自被测对象；7 收尾依赖全部。

```json
{
  "waves": [
    { "wave": 1, "tasks": ["1", "2", "4"] },
    { "wave": 2, "tasks": ["3", "5.3"] },
    { "wave": 3, "tasks": ["5.1", "5.2", "6"] },
    { "wave": 4, "tasks": ["7"] }
  ],
  "dependencies": {
    "1": [],
    "2": [],
    "4": [],
    "3": ["1", "2"],
    "5.1": ["1"],
    "5.2": ["3"],
    "5.3": ["4"],
    "6": ["3", "4"],
    "7": ["5.1", "5.2", "5.3", "6"]
  }
}
```



## Tasks

- [x] 1. 新增 ConsultationSummary 总结服务
  - 在 `app/agents/consultation_summary.py` 创建 `ConsultationSummary` 类，构造函数接收可选 `llm: LLMInterface | None`
  - 实现 `summarize(transcript, recommendations) -> str`：有 llm 时构造“仅基于给定客服内容做要点总结、不新增事实、简明中文”的 prompt 调 `llm.generate`；捕获异常回退规则
  - 实现规则回退：从 transcript 已有结构或 recommendation 的 reason/positives/negatives 抽取 3~5 行要点，保证非空且不臆造价格/星级
  - _Requirements: 3.1, 3.2, 3.4, 3.5, 5.2, 5.3_

- [x] 2. 扩展数据模型
  - 在 `app/api/models.py` 新增 `ConsultationSummaryResponse(ConsultationResponse)`，增加 `summary: str` 与 `transcript: str` 字段
  - 保持 `reply` 语义为面向用户的总结，确保前端 `data.reply` 兼容
  - _Requirements: 5.4_

- [x] 3. 新增 /consult/summary 端点并装配 LLM
  - 在 `_Components` 中新增 `self.llm = container.llm()`
  - 在 `app/api/routes.py` 新增 `POST /consult/summary`：取会话推荐，空→409；`product_ids` 筛选，无匹配→400
  - 调用 `CustomerService.answer` 得 transcript，再调用 `ConsultationSummary(llm).summarize` 得 summary
  - 返回 `ConsultationSummaryResponse(reply=summary, summary=summary, transcript=transcript, recommendations=selected)`
  - _Requirements: 2.1, 2.2, 2.3, 3.3, 5.1_

- [x] 4. SSE 事件增加 consult_offer 标志
  - 在 `/chat/stream` 的 `recommendations` 事件 payload 中加入 `"consult_offer": bool(recs)`
  - _Requirements: 1.1, 1.2_

- [x] 5. 后端测试
- [x] 5.1 ConsultationSummary 单测
  - MockLLM 下返回非空且含要点结构；`llm=None` 走规则回退非空且无臆造数值；LLM 抛异常时回退不抛出
  - _Requirements: 3.1, 3.4, 3.5, 5.3_
- [x] 5.2 /consult/summary API 单测（TestClient）
  - 有推荐→200 且含 summary/transcript/recommendations 且 `reply==summary`；无推荐→409；product_ids 无匹配→400；子集只总结选中商品
  - _Requirements: 2.1, 2.2, 2.3, 3.3, 5.4_
- [x] 5.3 SSE consult_offer 断言
  - 推荐非空时事件含 `consult_offer:true`，无推荐时为 false
  - _Requirements: 1.1, 1.2_

- [x] 6. 前端：推荐后咨询选项与总结气泡
  - 在推荐渲染后、当 `consult_offer` 为真时，于推荐卡片区下方渲染 `.consult-offer`（两个按钮：需要咨询 / 不需要）；无推荐不渲染
  - “需要咨询”：按钮进入 loading，`fetch("/consult/summary")` 带本轮全部推荐的 `product_ids`；成功后用 `aiBubble()` 把 `data.reply` 作为助手气泡追加到对话流，并标记该 Offer 已处理、隐藏按钮；失败恢复按钮并提示重试
  - “不需要”：隐藏 Offer、不发请求、保留推荐、可继续输入
  - 复用现有右侧客服面板展示原始 transcript（可选）
  - 中文文案，与现有客服风格一致
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 2.4, 3.3, 4.1, 4.2, 4.3_

- [x] 7. 验证与回归
  - `.venv\Scripts\python.exe -c "import main"` 导入校验；`pytest -q` 全绿
  - 启动服务，`Invoke-WebRequest` 校验页面含咨询选项相关元素与处理函数
  - in-process 校验 `/consult/summary` 各分支行为
  - _Requirements: 5.1, 5.3_

## Notes

- 复用现有 `/consult`、`CustomerService`、`LLMInterface` 与前端客服面板，改动最小、与既有编排一致。
- 无 LLM 环境（MockLLM）下总结走规则回退，保证不报错。
- 未改动 `.env`；完成后按团队 Git Flow 走 feature 分支 + PR（base=develop）。