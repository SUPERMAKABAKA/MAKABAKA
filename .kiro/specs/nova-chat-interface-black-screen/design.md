# nova-chat-interface-black-screen Bugfix Design

## Overview

Nova 是一个由 `static/index.html` 直接提供的单文件前端。用户报告认证相关启动或视图生命周期中出现全黑屏；现有需求要求覆盖首次打开、`#/auth`、登录成功、已有 token 启动、app 刷新和登出回退六条路径。

本设计先做 bug-condition exploration，再基于浏览器证据选择最小修复。修复目标是使每个合法启动/切换终态都满足“恰好一个顶层视图可见、该视图有可见且可交互内容、boot/setView/enterApp 路径无未捕获异常”。在证据确认前，不把重复函数定义、重复事件绑定、CSS 级联或任何特定异常当作已证实根因。

生产改动边界严格限定为 `static/index.html` 中认证后 `#appScreen` 的启动、app CSS/DOM 与 chat/lifecycle 相关代码；不改认证 API 或 storage 语义，不改 welcome/auth 的表现，不改后端、Agent、prompts、recommendation payload，也不改其他 spec、应用代码或测试代码。本阶段只创建本规格文档，不实现修复。

## Glossary

- **Bug_Condition (C)**：六条合法启动或生命周期路径中，三个顶层视图均不可见，或按当前流程应可见的视图没有可见/可交互内容。
- **Property (P)**：对满足 C 的输入，修复后的路径应完成到一个可见、可交互的正确视图，并且没有未捕获异常。
- **Preservation**：对不满足 C 的路径，认证、welcome/auth、chat/session/SSE、推荐数据和后端契约保持现有语义。
- **顶层视图**：`#welcomeScreen`、`#authScreen`、`#appScreen`；当前 HTML 初始均带有 `hidden` class。
- **`setView(name)`**：当前单文件中的视图切换函数，通过切换三个顶层元素的 `hidden` class 并同步 `body.front` 选择当前视图。
- **`enterApp()`**：认证成功或已有认证状态启动时进入 `#appScreen` 的生命周期入口，并更新用户显示与 app welcome visuals。
- **`isBugCondition(observation)`**：从浏览器观测中判断某条合法路径是否实际出现全黑屏。
- **`expectedBehavior(observation)`**：判断修复后路径是否有恰好一个可见顶层视图、可见交互内容且没有未捕获异常。

## Bug Details

### Bug Condition

探索必须优先于根因结论。每次浏览器运行需记录路径、操作顺序、token/username 状态、三个顶层视图的 `hidden` class 与 computed `display/visibility/opacity`、当前视图的可见文本和可交互控件、console error、`window.onerror`/`unhandledrejection`、网络/资源错误和最小复现步骤。

静态结构显示：三个顶层节点在 HTML 中均以 `hidden` class 开始；`.hidden` 使用 `display:none!important`；启动脚本末尾依据 token/hash 调用 `enterApp()` 或 `setView()`；登录成功调用 `enterApp()`；登出调用 `enterWelcome()`。这些是可核对事实，不代表黑屏根因已知。

**Formal Specification:**

```text
FUNCTION isBugCondition(observation)
  INPUT: observation of one legal startup or lifecycle path
  OUTPUT: boolean

  legalPath := observation.path IN {
    first_open,
    direct_auth_hash,
    login_success,
    existing_token_boot,
    app_refresh,
    logout_to_welcome
  }

  visibleCount := count of {
    #welcomeScreen, #authScreen, #appScreen
  } whose computed display is not none,
  visibility is not hidden, and effective content is visible

  RETURN legalPath
         AND (
           visibleCount = 0
           OR expectedViewHasNoVisibleInteractiveContent(observation)
         )
END FUNCTION
```

### Exploration-First Runtime Evidence

探索检查应在未修复代码上先运行，并按以下六个最小场景捕获证据；场景是否真的失败必须由浏览器观测决定：

1. **首次打开**：清除 `nova_token`/`nova_user`，打开根路径；等待脚本和首屏稳定，记录 welcome 是否可见。
2. **直接 auth hash**：清除认证状态，打开 `#/auth`；记录 auth card、输入框和提交按钮是否可见/可交互。
3. **登录成功**：从 auth 提交一组合法测试凭据，记录 `authSucceeded()` 到 `enterApp()` 的转换和 app 内容。
4. **已有 token 启动**：预置合法 `nova_token` 与 `nova_user` 后冷启动根路径；记录是否直接进入 app。
5. **app 刷新**：在已认证 app 中刷新；记录刷新前后 token、视图数量、app 内容和异常。
6. **登出回 welcome**：在 app 中触发 Sign out；记录清理后的 storage、history/hash、welcome 内容和异常。

若未修复代码上的 exploration test **按预期失败**，失败就是成功捕获 bug 的证据，应保存最小复现、视图快照和错误信息后继续；若 exploration **意外通过**，必须停止后续实现规划并报告，先重新确认复现条件，不能为了让测试失败而改测试或臆造根因。

### Concrete Manifestation Examples

以下是待在未修复代码上执行并记录的具体例子，而不是预先断言已经发生的事实：

- `localStorage` 同时存在合法 token/username，刷新根路径后 `#welcomeScreen`、`#authScreen`、`#appScreen` 的可见计数为 `0`，且 console 出现未捕获异常：这是 `existing_token_boot` 的 bug-condition 反例；应改为可见 app。
- 无 token 访问 `/#/auth` 后 auth card 不可见或三个顶层节点仍全部隐藏：这是 `direct_auth_hash` 的反例；应改为唯一可见的 auth。
- 使用合法账号登录后 URL 已变为 `#/app`，但 app shell 无可见交互内容或转换期间出现 `unhandledrejection`：这是 `login_success` 的反例；应改为唯一可见的 app。
- app 刷新后页面空白，而登出后 welcome 可见（或反之）：记录两条路径的差异，避免把单一路径的观察泛化为所有生命周期路径。

## Expected Behavior

### Restoration Strategy

修复后对六条合法路径统一执行以下恢复策略：

1. 启动/切换终态必须由一个受控 lifecycle 入口决定；不能通过隐藏全部顶层视图表示正常等待。
2. 进入目标状态时，必须保证 `#welcomeScreen`、`#authScreen`、`#appScreen` 中恰好一个为有效可见状态；其他两个保持隐藏。
3. 在 `setView()`、`enterApp()` 和 boot 相关路径发生异常时，必须由 exploration 证据确定最小保护位置；不得吞掉认证错误或改写 API/storage 语义。
4. app 仅在认证后路径恢复；未认证状态仍按现有 welcome/auth 路由表现，认证成功仍按现有 API 返回值和 token/username 存储语义进入 app。
5. 修复不得重构聊天、SSE、session、recommendation 或后端调用；仅修复导致 app 无法显示或生命周期无法完成的最小启动/lifecycle 问题。

### Preservation Requirements

**Unchanged Behaviors:**

- 认证请求、成功/失败处理、`nova_token`/`nova_user` 存储和现有路由语义保持不变。
- welcome/auth 的视觉呈现、表单、密码显示、错误提示、Back/Start 行为保持不变。
- app 的 chat/session、消息发送、`POST /chat/stream` SSE 处理、响应渲染与 loading 状态保持不变。
- recommendation payload、排序/内容语义、ReAct details、购物浏览面板和 Nova assistant 行为保持不变。
- 后端 API、路由、Agent、prompts、请求/响应契约和非 app 代码不发生行为性变化。

**Scope:**

所有不满足 `isBugCondition` 的合法输入必须保持修复前可见结果和交互结果，除非该结果违反本规格的启动不变量。尤其不得把“恢复 app 可见”扩展成修改 welcome/auth 表现、认证 API/storage、后端或推荐数据。

## Hypothesized Root Cause

以下均为待证实假设，必须由 exploration 的 console/uncaught exception、视图快照和最小复现支持后才能用于实现：

1. **Lifecycle 转换没有完成或被异常中断（待证实）**：boot、`setView()`、`enterApp()` 或相关启动回调可能在完成唯一可见视图设置前抛错，留下三个顶层视图均隐藏。需要用事件时序、异常堆栈和每一步 class/computed style 证明。
2. **CSS/DOM 可见性状态不一致（待证实）**：当前 `.hidden{display:none!important}` 与 `#appScreen` 的 grid/display 样式同时存在；需要检查 computed style、class 变更时间和实际布局矩形，确认是否有 CSS 级联或属性残留导致 app 内容不可见。
3. **旧逻辑与 redesign override 的交互造成运行时副作用（待证实）**：静态检查可见多个同名函数定义（例如 `autosize`、`saveSession`、`switchToSession`、`fitEmbed`、`doSend` 等）以及多处事件绑定。重复定义/绑定本身不是证据；只有当捕获到其调用顺序导致的异常或视图状态破坏时，才能纳入最小修复。
4. **浏览器能力或资源初始化失败（待证实）**：例如 `ResizeObserver`、canvas、外部字体/资源或其他初始化 API 失败，可能在 boot 前终止脚本。需记录资源失败、浏览器版本和具体堆栈；不能用浏览器兼容性猜测替代证据。
5. **认证状态/URL 时序不一致（待证实）**：token、username、hash 与 history 状态可能在刷新、登录成功或登出期间出现不一致。需对 storage、hash、history 和视图快照做同一时刻记录。

### Root-Cause Evidence Gate

只有满足“最小复现可重复 + 触发操作明确 + console/uncaught exception 或 computed visibility 证据明确 + 能将异常/状态变化连接到黑屏结果”时，才能把某个假设标记为 confirmed。若无异常但所有视图均隐藏，应继续追踪 `setView`/class 变更与 CSS computed style；不得以“有重复定义”作为单独根因。

## Correctness Properties

Property 1: Bug Condition - Authenticated Startup and View Lifecycle Restoration

_For any_ legal startup/lifecycle observation where `isBugCondition(observation)` returns true, the fixed `static/index.html` SHALL complete the path without an uncaught exception, make exactly one of `#welcomeScreen`, `#authScreen`, and `#appScreen` visible, and provide visible interactive content appropriate to that path. For authenticated startup and refresh this is app content; for direct auth and logout it is auth/welcome content as specified.

**Validates: Requirements 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 2.8**

Property 2: Preservation - Protected Authentication and App Behavior

_For any_ legal input where `isBugCondition(observation)` returns false, the fixed implementation SHALL preserve the original authentication API/storage semantics, welcome/auth presentation and interaction, chat/session/SSE behavior, recommendation payload semantics, and protected backend/Agent/prompt contracts; the only allowed visible difference is restoration of the startup invariant where the original state was defective.

**Validates: Requirements 2.9, 3.1, 3.2, 3.3, 3.4, 3.5, 3.6**

## Fix Implementation

### Changes Required

实施阶段必须先使用 exploration 结果选择以下最小变更，不得同时做无证据的重复定义清理或 redesign 重构：

1. **修复已证实的启动/lifecycle 中断点**：只在 `static/index.html` 中的 boot、`setView()`、`enterApp()` 或其直接 app lifecycle 依赖处修改，使合法路径能够完成视图转换；具体位置和代码形式以异常堆栈/状态快照为准。
2. **落实单一顶层可见状态**：若证据显示存在状态竞争或残留 class，只补充最小的互斥状态处理，使每次终态满足可见计数为 1；不改变 welcome/auth 路由语义。
3. **保留认证边界**：不改 `/auth/login`、`/auth/register`、token/username key、错误消息语义、history 规则或登录成功判定。
4. **保留 app 行为**：不改 `/chat/stream`、Authorization header、session 生命周期、SSE 事件解释、recommendation payload 或后端/Agent/prompts。
5. **控制 diff**：只允许与认证后 `#appScreen` 启动、app CSS/DOM/chat lifecycle 和顶层视图生命周期直接相关的行；若需要检查辅助代码，必须 dependency-free 且不改变生产运行时语义。

### Implementation Decision Record

实施任务必须记录：

- 已复现的路径和最小输入；
- 修复前三个顶层视图的可见性与 computed style；
- console error/uncaught exception 的实际消息和堆栈（若有）；
- 排除的假设及排除证据；
- 选择的最小代码改动和为什么不会触碰保护边界。

## Testing Strategy

### Validation Approach

测试严格按“探索 → 观察并编写 preservation → 实施 → 验证”的顺序。浏览器诊断应拦截 console error、`window.onerror`、`unhandledrejection`，并在每个关键转换前后采集三视图快照。若未修复 exploration 意外通过，立即停止并报告，不进入实现任务。

### 1. Bug-Condition Exploration (必须先于修复)

**Goal**：在未修复代码上捕获实际全黑屏路径、视图可见性、console/uncaught exception、最小复现和根因证据。

**Test Plan**：运行 requirements 4.1 列出的六条路径；每条保存结构化诊断记录。至少断言：路径合法；三个顶层视图的可见计数；当前区域有可见文本/控件；console error 与 uncaught exception 数量；token/hash 状态；复现步骤完整。

**Expected outcomes**：

- 若断言在未修复代码上失败，失败是预期结果，表示成功捕获 bug；保存 counterexample 后继续。
- 若六条路径均通过，或目标 exploration test 意外通过，必须停止并报告，重新核对环境、凭据、浏览器和复现前提；不得继续假定存在黑屏或修改测试以制造失败。

### 2. Preservation Observation (修复前)

对 `isBugCondition` 为 false 的路径先观察未修复行为，再把实际结果编码为 preservation checks，并确认这些 checks 在未修复代码上通过。范围包括认证失败/成功语义、welcome/auth 交互、已有正常 app 的 chat/session/SSE、推荐结果展示和 logout storage 清理。不能凭假设写“应该保持”，必须记录实际 baseline。

### 3. Fix Checking

```text
FOR ALL observation WHERE isBugCondition(observation) DO
  result := run_fixed_browser_path(observation.path)
  ASSERT expectedBehavior(result)
END FOR
```

`expectedBehavior` 至少检查：无 uncaught exception；`visibleTopLevelViewCount = 1`；当前视图有可见且可交互内容；认证后启动/刷新为 app；direct auth 为 auth；logout 为 welcome。

### 4. Preservation Checking

```text
FOR ALL observation WHERE NOT isBugCondition(observation) DO
  ASSERT protected_behavior_original(observation)
         = protected_behavior_fixed(observation)
END FOR
```

比较内容应包含认证请求/storage、welcome/auth DOM 与交互、chat/session/SSE 最小流程、推荐 payload/渲染语义和后端调用边界；允许的唯一差异是修复违规的启动可见性不变量。

### Unit Tests

- 对 `setView()`/boot/lifecycle 的可见性状态做最小 DOM 检查：六种路径终态恰好一个顶层视图可见。
- 对 `window.onerror` 与 `unhandledrejection` 做路径级断言，覆盖异常中断导致的全隐藏状态。
- 对 token/username 存在、缺失、登出清理和 `#/auth` 路由分支做边界检查。
- 对不涉及黑屏的认证失败、密码显示和 welcome/auth 交互做 preservation baseline 检查。

### Property-Based Tests

- **Property 1**：在合法路径状态（token/hash/操作序列）生成或枚举组合，断言 bug-condition 输入修复后完成唯一可见视图和正确内容；对于确定性浏览器缺陷，可将策略限定为六个具体最小路径并保留重复运行。
- **Property 2**：对不触发黑屏的认证、视图、chat/session 状态生成组合，比较修复前 baseline 与修复后受保护行为；覆盖空/非空 session、失败响应、正常响应和无推荐结果等现有输入。
- 视图互斥不变量：任何合法 boot/setView/enterApp 终态的 visible top-level count 均为 1，且异常计数为 0。

### Integration Tests

- 浏览器启动 smoke：首次打开与 direct `#/auth`。
- 认证生命周期 smoke：合法登录进入 app、已有 token 冷启动、app 刷新、logout 回 welcome。
- 受保护页面回归：welcome/auth 视觉与表单行为、认证请求/storage、错误处理。
- app 行为回归：输入框、session 入口、最小 `POST /chat/stream` SSE 发送/响应、recommendation payload 与现有推荐交互。
- 最终检查：HTML 结构、JavaScript syntax、console/uncaught exception、六条路径可见性和 diff boundary；确认没有修改后端、Agent、prompts、recommendation payload、应用测试或 `nova-chat-interface-redesign` spec。
