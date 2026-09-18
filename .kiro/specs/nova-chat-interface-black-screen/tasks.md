# Implementation Plan

本任务列表遵循：**探索 → preservation 观察 → 最小实现 → 路径回归 → 最终验证**。除任务 1 明确记录的预期失败外，不得通过修改测试来消除失败；所有生产改动必须受 design.md 的 evidence gate 与 diff boundary 约束。

- [x] 1. **Property 1: Bug Condition** - 在未修复代码上执行六路径浏览器启动/生命周期探索
  - **依赖**：无。
  - **必须先于任何修复执行**；使用浏览器或等价真实 DOM smoke harness，覆盖：首次打开、直接访问 `#/auth`、合法登录进入 app、已有 `nova_token`/`nova_user` 启动、app 刷新、登出回 welcome。
  - 按 design.md 的 `isBugCondition(observation)` 采集每条路径的：触发操作、最小复现步骤、token/username/hash、`#welcomeScreen`/`#authScreen`/`#appScreen` 的 class 与 computed `display/visibility/opacity`、可见文本/控件、console error、`window.onerror`、`unhandledrejection`、资源错误和堆栈。
  - 断言每条路径最终应有恰好一个可见顶层视图和可交互内容；在未修复代码上若按预期失败，**该失败表示成功捕获 bug**，必须保存 counterexample 后标记完成。
  - 若 exploration 意外通过，**立即停止并报告**，不要继续实现、不要改测试制造失败；先重新核对浏览器、凭据、storage、hash 和复现前提。
  - 输出：六路径诊断记录、实际失败路径清单、最小复现步骤和根因证据/未知项。
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 4.1, 4.2, 4.4, 4.5, 4.6_

- [x] 2. **Property 1: Bug Condition** - 对 `static/index.html` 做启动顺序、HTML/JS 与可见性静态检查
  - **依赖**：1（先取得运行时证据，再用静态检查解释证据）。
  - 核对真实结构：三个顶层节点均以 `hidden` class 开始；`.hidden` 的 `display:none!important`；`setView()` 对三个节点的 class 切换；boot 末尾的 token/hash 分支；`authSucceeded()`/`enterApp()`；logout/`enterWelcome()`。
  - 记录旧逻辑与 redesign override 的同名函数、重复事件绑定、`ResizeObserver`/canvas 等运行时依赖作为**待证实风险**；不得把重复定义直接写成已证实根因。
  - 执行可用的 HTML 结构检查和 JavaScript syntax 检查，记录解析错误、脚本提前终止和与任务 1 对应的调用堆栈；若静态检查无法执行，记录替代检查方式。
  - 输出：结构/顺序检查结果、与黑屏反例关联的候选位置、尚未证实的假设和排除证据。
  - _Requirements: 4.2, 4.3, 4.11_

- [x] 3. **Property 2: Preservation** - 在未修复代码上观察并编写 preservation baseline
  - **依赖**：1、2；必须在实现前完成。
  - 遵循 observation-first：先运行未修复代码，再将实际通过行为编码为 preservation checks，并确认 checks 在未修复代码上通过。
  - 覆盖认证失败与成功的 API/storage 语义、welcome/auth 视觉与交互、已有正常 app 的 chat/session、最小 `POST /chat/stream` SSE、推荐 payload/渲染、登出清理 storage 和 hash。
  - 明确排除 `isBugCondition` 返回 true 的路径；记录 baseline 的可见结果、DOM 关键状态、请求方法/路径/headers/响应语义和用户交互结果。
  - 输出：可重复 preservation 测试/记录、未修复代码通过证据、受保护行为对照表。
  - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 4.10, 4.12_

- [x] 4. 实施基于证据的 `static/index.html` 最小启动/lifecycle 修复
  - **依赖**：1、2、3；只有探索失败已保存且根因达到 design.md evidence gate 后才能开始。
  - 修复范围仅限认证后 `#appScreen` 启动、app CSS/DOM/chat lifecycle 和顶层视图生命周期；不得修改认证 API/storage、welcome/auth 表现、后端、Agent、prompts、recommendation payload、应用测试或 `nova-chat-interface-redesign` spec。
  - 不得因静态上存在重复定义就直接重构；只有任务 1/2 证实其造成黑屏时才可做与该证据直接对应的最小修改。
  - _Bug_Condition: `isBugCondition(observation)` from design.md；仅处理实际捕获的六路径黑屏状态。
  - _Expected_Behavior: `expectedBehavior(result)`；无未捕获异常、恰好一个顶层视图可见、当前状态有可见可交互内容。
  - _Preservation: design.md Preservation Requirements；保留认证、welcome/auth、chat/session/SSE、recommendation 和后端契约。
  - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 2.8, 2.9, 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 4.11_

  - [x] 4.1 **Property 1: Expected Behavior** - 重跑同一探索检查并确认 bug-condition 路径修复
    - **依赖**：4。
    - 必须重跑任务 1 的同一组检查，不得另写一个只会通过的新测试；覆盖实际失败的路径以及六路径完整集合。
    - 断言修复后无 console error/uncaught exception，且每条路径最终 visible top-level count 恰好为 1、内容可见且交互可用。
    - 预期结果：任务 1 的反例全部消失并通过；若仍失败，回到根因证据，不扩大修复范围。
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 2.8, 4.4, 4.5, 4.6_

  - [x] 4.2 **Property 2: Preservation** - 重跑同一 preservation checks 并确认无回归
    - **依赖**：4。
    - 必须重跑任务 3 的同一组 baseline/preservation checks，不得另写一个绕开保护行为的新测试。
    - 认证 API/storage、welcome/auth、chat/session/SSE、recommendation payload 和后端边界必须与未修复 baseline 一致。
    - 预期结果：preservation checks 继续通过；任何差异都先判定为回归并修复或停止。
    - _Requirements: 2.9, 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 4.10, 4.12_

  - [x] 4.3 记录实现决策与 diff boundary 审计
    - **依赖**：4.1、4.2。
    - 记录确认根因、实际错误/堆栈、排除假设、最小变更理由；检查生产 diff 只包含允许的 `static/index.html` 范围。
    - _Requirements: 4.2, 4.6, 4.11_

- [x] 5. 验证顶层视图互斥可见性回归
  - **依赖**：4.1、4.2。
  - 在首次打开、direct `#/auth`、登录成功、已有 token 启动、app 刷新、登出回 welcome 六个终态读取三个顶层节点的 computed visibility。
  - 断言任一终态 visible top-level count 恰好为 1；可见视图有可见文本和必要可交互控件；不存在全隐藏或多个活动顶层视图。
  - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.8, 4.5_

- [x] 6. 验证已有合法 token 启动与 app 刷新
  - **依赖**：5。
  - 预置合法 `nova_token` 与 `nova_user`，冷启动根路径并检查直接进入可见 app；随后在 app 刷新并确认认证状态、app 内容、chat input 和 session 入口恢复。
  - 断言不改变 storage key/value 语义，不进入 welcome/auth，不产生 console error/uncaught exception。
  - _Requirements: 2.4, 2.5, 2.7, 4.7, 4.9_

- [x] 7. 验证登录成功进入 app
  - **依赖**：5；使用任务 3 的合法测试账号/认证 baseline。
  - 从 `#/auth` 提交合法凭据，确认现有认证请求和 token/username 持久化语义不变；等待 `authSucceeded()`/`enterApp()` 完成。
  - 断言唯一可见视图为 app，chat input、session 入口和现有 app 内容可交互；auth success 表现不被改变为伪造成功或跳过 API。
  - _Requirements: 2.3, 2.7, 4.8, 4.10_

- [x] 8. 验证刷新与登出回 welcome 生命周期
  - **依赖**：6、7。
  - 已认证 app 刷新一次并保存视图/异常证据；随后触发 Sign out，检查 token/username 清理、history/hash 更新、welcome 内容恢复。
  - 断言刷新最终为唯一可见 app；登出最终为唯一可见且可交互 welcome；两条路径无全黑屏、无 uncaught exception，且认证与路由语义保持 baseline。
  - _Requirements: 2.5, 2.6, 2.7, 3.1, 4.7, 4.9_

- [x] 9. 受保护 welcome/auth 页面回归
  - **依赖**：7、8。
  - 回归首次 welcome、Start/Sign in、direct `#/auth`、Sign in/Create account 切换、密码显示、认证失败提示、Back to home；比较任务 3 的未修复 baseline。
  - 断言修复没有改变 welcome/auth 的视觉、交互、表单、错误处理或认证请求/storage 语义；只接受修复启动不变量造成的必要可见性恢复。
  - _Requirements: 3.1, 3.2, 4.10_

- [x] 10. app chat/session/SSE 与受保护 payload 回归
  - **依赖**：6、7、9。
  - 在可见 app 中完成最小消息发送、`POST /chat/stream` SSE token/recommendations/error 处理、session 新建/切换、推荐结果和现有 app 入口检查。
  - 断言 Authorization header、session 生命周期、响应渲染、recommendation payload/排序/内容语义和 Agent/prompts/backend 行为不变；不把后端失败误判为本黑屏修复成功或失败。
  - _Requirements: 2.9, 3.3, 3.4, 3.5, 4.12_

- [x] 11. 最终验证与交付检查
  - **依赖**：4.3、5、6、7、8、9、10。
  - 运行可用的 HTML 结构检查和 JavaScript syntax 检查；重跑六路径 browser smoke 与 console/uncaught exception 诊断；确认任务 1 的 counterexample 已消失。
  - 审计 git diff：仅允许目标 bugfix spec 文档以及实施阶段被明确允许的 `static/index.html` app startup/lifecycle 范围；本规格创建阶段不得改应用代码、测试代码或其他 spec。
  - 确认所有 requirements 4.1–4.12 均有测试/记录追踪；若任一检查失败，停止交付并回到对应任务，不用弱化断言。
  - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7, 4.8, 4.9, 4.10, 4.11, 4.12_

- [x] 12. Checkpoint - 确认所有检查通过后再交付
  - **依赖**：11。
  - 汇总探索反例、确认根因、最小修复、preservation 结果、六路径终态可见性与异常计数。
  - 若 exploration 意外通过、根因证据不足、出现保护边界外 diff 或任一回归失败，标记为阻塞并报告，不得声称 bugfix 完成。
  - _Requirements: 2.7, 3.6, 4.1, 4.2, 4.4, 4.5, 4.6, 4.10, 4.11_
