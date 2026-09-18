# Requirements Document

## Introduction

本规格用于处理 Nova 前端在认证相关启动或视图切换过程中出现“全黑屏”的问题。前端由 `static/index.html` 直接提供，是无构建步骤的单文件 HTML/CSS/JS 应用；顶层视图为 `#welcomeScreen`、`#authScreen` 和 `#appScreen`，由 `setView()` 与 `.hidden` 状态切换。认证成功后调用 `enterApp()`；启动阶段在存在 token 和 username 时也会直接进入 app。

当前 `static/index.html` 同时保留旧 app 样式/聊天逻辑以及后续 redesign override/逻辑，因此重复定义和重复事件绑定是需要在后续探索中核查的风险，但本需求不把它们当作已经证实的根因。

本规格只覆盖认证后 app 的启动与生命周期稳定性。修复应保持现有认证、聊天、session、SSE 及后端行为不变，并提供足够的探索与回归验证，以捕获实际浏览器证据后再确定根因。

## Requirements

### Bug Analysis

#### Current Behavior (Defect)

下列行为描述的是用户报告的可观察缺陷及需要验证的可能触发条件；当前尚未有浏览器控制台错误、精确触发路径或最小复现步骤，因此不得把某个具体异常当作既定事实。

1.1 WHEN 用户首次打开应用并执行正常启动流程 THEN 系统可能使 `#welcomeScreen`、`#authScreen`、`#appScreen` 均不可见，或使当前应显示的区域没有任何可见内容，表现为全黑屏。

1.2 WHEN 用户直接访问 `#/auth` THEN 系统可能无法显示可交互的认证视图，或在视图切换过程中进入全黑屏。

1.3 WHEN 用户完成登录并由 `enterApp()` 进入 app THEN 系统可能无法显示可交互的 app 内容，或所有顶层视图均不可见。

1.4 WHEN 应用启动时 localStorage 中已有合法 token 和 username 并直接进入 app THEN 系统可能在启动阶段进入全黑屏，且用户无法确认 app 是否已成功初始化。

1.5 WHEN 用户在 app 视图刷新页面 THEN 系统可能未恢复可见的 app 内容，或在启动恢复过程中使所有顶层视图不可见。

1.6 WHEN 用户从 app 登出并应回退到 welcome THEN 系统可能未显示 welcome 内容，导致登出后仍处于全黑屏；该路径必须与“正确回退到 welcome”区分验证。

#### Bug Condition Exploration

探索测试必须覆盖 1.1–1.6 的每条路径，并记录每次运行的启动状态、视图状态、可见内容、浏览器 console error、未捕获异常、触发操作和最小复现步骤。探索结果必须区分：

- **全黑屏**：三个顶层视图都不可见，或按当前流程应可见的区域没有任何可见内容/可交互内容。
- **正常状态**：恰好一个顶层视图可见，并包含该状态应有的可见且可交互内容。
- **未知根因**：在捕获 console exception、uncaught exception 或其他证据前，不将重复定义、重复事件绑定、特定函数异常或 CSS 原因写成事实。

**Bug Condition Function**

```text
FUNCTION isBugCondition(observation)
  INPUT: observation of one legal startup or lifecycle path
  OUTPUT: boolean

  RETURN observation.path IN {
           first_open,
           direct_auth_hash,
           login_success,
           existing_token_boot,
           app_refresh,
           logout_to_welcome
         }
         AND (
           visibleTopLevelViewCount(observation) = 0
           OR expectedViewHasNoVisibleContent(observation)
         )
END FUNCTION
```

**Evidence requirement**：`isBugCondition` 的判断以浏览器实际观测为准。若路径正常，不得将其标记为缺陷；若路径黑屏，必须保存当时的视图可见性、console/uncaught exception 状态及可复现步骤。

#### Expected Behavior (Correct)

2.1 WHEN 用户首次打开应用并执行正常启动流程 THEN 系统 SHALL 显示可见且可交互的 welcome 或 auth 内容，并且恰好一个顶层视图可见。

2.2 WHEN 用户直接访问 `#/auth` THEN 系统 SHALL 显示可见且可交互的认证视图，并且恰好一个顶层视图可见。

2.3 WHEN 用户完成登录并由 `enterApp()` 进入 app THEN 系统 SHALL 显示可见且可交互的 app 内容，并且恰好一个顶层视图可见。

2.4 WHEN 应用启动时 localStorage 中已有合法 token 和 username THEN 系统 SHALL 直接显示可见且可交互的 app 内容，并且恰好一个顶层视图可见。

2.5 WHEN 用户在 app 视图刷新页面 THEN 系统 SHALL 根据当前合法认证状态恢复可见且可交互的 app 内容，并且恰好一个顶层视图可见。

2.6 WHEN 用户从 app 登出 THEN 系统 SHALL 清理现有认证状态所要求的内容并显示可见且可交互的 welcome 内容，且不得出现全黑屏。

2.7 WHEN boot、`setView()` 或 `enterApp()` 处理任一合法启动/切换状态 THEN 系统 SHALL 不抛出未捕获异常，并 SHALL 完成到一个可见顶层视图的状态转换。

2.8 WHEN 应用处于未认证或已认证的任一合法状态 THEN 系统 SHALL 提供该状态对应的可见内容和必要的交互入口；不得通过隐藏全部顶层视图表示正常等待状态。

2.9 WHEN app 已成功显示并且用户使用现有聊天功能 THEN 系统 SHALL 继续支持既有 chat/session 行为、消息发送、`POST /chat/stream` SSE 流式响应、响应渲染和相关生命周期，不因黑屏修复而改变其语义。

**启动不变量**：对任意合法启动状态，`visibleTopLevelViewCount` 必须等于 1；boot、`setView()`、`enterApp()` 不得产生未捕获异常；当前可见视图必须包含可见内容和可用交互。

#### Unchanged Behavior (Regression Prevention)

3.1 WHEN 认证表单提交、认证失败、认证成功或认证状态恢复 THEN 系统 SHALL CONTINUE TO 使用现有认证请求、路由、token/username 存储语义及错误处理语义。

3.2 WHEN 用户访问 welcome 或 auth 页面 THEN 系统 SHALL CONTINUE TO 保持现有 welcome/auth 的视觉呈现、交互行为、表单行为和页面切换语义。

3.3 WHEN app 发起聊天请求或处理 SSE 流 THEN 系统 SHALL CONTINUE TO 使用现有 API、请求/响应协议、session 管理、消息渲染和加载状态行为。

3.4 WHEN app 显示推荐结果、ReAct details、购物浏览面板或 Nova assistant THEN 系统 SHALL CONTINUE TO 保持现有 recommendation payload、排序/内容语义及既有交互行为。

3.5 WHEN 后端 API、路由、Agent、prompts 或 recommendation payload 被调用 THEN 系统 SHALL CONTINUE TO 保持其接口、数据结构和行为不变。

3.6 WHEN 对不触发全黑屏的合法路径执行回归测试 THEN 系统 SHALL CONTINUE TO 产生与修复前一致的用户可见结果和交互结果，除非该结果违反本规格的启动不变量。

### Acceptance Criteria

4.1 **路径覆盖**：探索检查 SHALL 覆盖首次打开、直接访问 `#/auth`、登录成功后进入 app、已有 localStorage token 启动、刷新 app、登出回退 welcome 六条路径，并为每条路径记录触发状态和最小复现步骤。

4.2 **缺陷证据**：若某条路径触发 `isBugCondition`，检查 SHALL 记录三个顶层视图的可见性、当前区域是否有可见/可交互内容、console error、uncaught exception 及可复现操作；不得用未经验证的具体异常替代证据。

4.3 **HTML/JS 有效性**：修复后的 `static/index.html` SHALL 通过可用的 HTML 结构检查和 JavaScript syntax 检查；检查不得因修复引入解析错误、重复初始化导致的未捕获异常或脚本提前终止。

4.4 **启动路径 smoke checks**：六条路径均 SHALL 完成一次可重复的浏览器或等价 smoke check；每条路径最终 SHALL 显示合法内容并保持可交互。

4.5 **视图互斥可见性**：在首次启动、auth hash、登录成功、已有 token 启动、app 刷新和登出回退的最终状态，顶层视图可见数量 SHALL 恰好为 1；不得出现全隐藏或多顶层视图同时作为活动视图的状态。

4.6 **异常检查**：boot、`setView()`、`enterApp()` 及路径转换期间 SHALL 没有 console error 或 uncaught exception；若存在异常，必须在进入实现阶段前记录其实际消息、堆栈（若有）和触发步骤。

4.7 **认证恢复**：使用合法 localStorage token 和 username 启动以及刷新 app SHALL 能进入可见 app；无合法认证状态时 SHALL 能进入可见 welcome/auth，且不发生黑屏。

4.8 **认证后进入 app**：从认证成功操作进入 app SHALL 显示现有 app 内容，并 SHALL 保留聊天输入、session 入口及现有 app 交互的可用性。

4.9 **刷新与登出回退**：刷新 app SHALL 恢复正确的认证视图；登出 SHALL 回退到可见 welcome，且两条路径均不得出现全黑屏或未捕获异常。

4.10 **受保护页面回归**：welcome/auth 的视觉和行为、认证请求与存储语义 SHALL 通过回归检查；后端 API、路由、Agent/prompts、recommendation payload 和非 app 代码 SHALL 没有行为性变化。

4.11 **diff boundary**：生产修改 SHALL 限定在 `static/index.html` 中与认证后 `#appScreen` 启动、app CSS/DOM/chat lifecycle 相关的代码；允许增加 dependency-free development checks，但不得修改后端、Agent、prompts、recommendation payload、现有测试语义或 `.kiro/specs/nova-chat-interface-redesign`。任何超出边界的 diff 都不满足验收标准。

4.12 **现有 app 行为保留**：修复后的 chat/session/SSE smoke check SHALL 成功完成最小消息发送和响应处理流程，且不改变既有 API 契约、session 生命周期或推荐数据语义。

### Scope and Protection Boundary

#### Allowed Production Changes

- `static/index.html` 中仅与认证后 `#appScreen` 启动、app CSS/DOM、app chat lifecycle 和视图生命周期相关的代码。
- 不依赖新增包的 development checks、浏览器检查脚本或等价验证辅助内容；这些检查不得改变生产运行时语义。

#### Protected Behavior and Files

- 不得改变后端 API、路由、请求方法、请求/响应契约或认证请求/存储语义。
- 不得改变 welcome/auth 的视觉、交互、表单行为或认证错误处理。
- 不得改变 Agent、prompts、recommendation payload、推荐排序/内容语义。
- 不得修改 `static/index.html` 中与保护边界无关的代码、应用源代码、测试代码或现有 `.kiro/specs/nova-chat-interface-redesign` spec。

### Known Unknowns and Follow-up Evidence

当前未知信息必须在后续 exploration test/browser check 中补齐，而不是在本需求中猜测：

- 实际触发全黑屏的最小路径究竟是哪一条或哪几条。
- 黑屏发生时的精确视图可见性、DOM 内容状态和认证状态。
- 是否存在 console exception、uncaught exception、资源加载错误或脚本提前终止；若存在，需记录实际错误消息和堆栈。
- 重复 app 样式/聊天逻辑定义或重复事件绑定是否与缺陷存在因果关系。
- 黑屏是否只发生在特定浏览器、刷新时序、localStorage 内容或 SSE/chat 初始化状态。

后续 design/tasks 必须以这些实际观测结果确认或修正根因假设，并遵循“先在未修复代码上运行 exploration checks，再编写并验证 preservation checks，最后实现修复”的顺序。本阶段不实现修复，也不创建 `design.md` 或 `tasks.md`。
