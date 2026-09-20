# Task 6 已有合法 token 启动与 app 刷新验证报告

## 结果

**静态 source-contract 与 MiniDOM 模型通过；真实 browser/runtime unavailable。** 本任务没有修改生产代码。验证确认当前 `static/index.html` 的认证恢复分支读取既有 `nova_token`/`nova_user`，两者同时存在时调用 `enterApp()`，并由 `enterApp()` 调用 `setView("app")`。MiniDOM 模型对 `existing_token_boot` 和 `app_refresh` 均得到唯一可见的 `appScreen`，但这不是浏览器 smoke pass。

## 验证命令

- 一次性 dependency-free source-contract check：`python ._task6_check.py`
  - 结果：**PASS**。
  - 检查后删除临时 helper；最终仅保留本报告和 JSON 证据。
- MiniDOM/control-flow：`python exploration_static_harness.py`
  - 结果：两条目标路径均完成模型检查。
  - 未使用浏览器，未执行 inline JavaScript。
- JavaScript syntax：`C:\\Program Files\\nodejs\\node.exe --check task6-inline-script.tmp.js`
  - Node：`v24.19.0`。
  - return code：`0`，stderr 为空。
  - 该命令只证明抽取出的 inline script 可被 Node 解析，不证明浏览器运行时无异常。

## Source-contract 结果

| 检查 | 结果 |
|---|---|
| 读取 `localStorage.getItem("nova_token")` | **PASS** |
| 读取 `localStorage.getItem("nova_user")` | **PASS** |
| token 与 username 同时存在时 boot 调用 `enterApp()` | **PASS** |
| `enterApp()` 调用 `setView("app")` | **PASS** |
| `setView()` 对三个顶层视图执行互斥 `hidden` 切换 | **PASS** |
| `enterApp()` 不改写认证 storage | **PASS** |
| app 内容 DOM 存在 | **PASS** |
| chat input `#input` 存在 | **PASS** |
| 新建 session 入口 `#newChat` 存在 | **PASS** |
| Recent/session 入口 `#sideToggle`、`#hist` 存在 | **PASS** |
| session store / `pushHistory()` 契约存在 | **PASS** |

当前源文件 SHA-256：`6789b06d739fa7cd80ef28dfdfb0eec694e6334fb161792de63d12b3bc781e09`。

## 目标路径模型结果

| 路径 | 操作 | 模型最终 storage | 预期视图 | 模型 visible top-level count | 内容/交互 |
|---|---|---|---|---:|---|
| `existing_token_boot` | 预置合法 token/user，冷启动 `/` | `nova_token=valid-token`、`nova_user=alice`，不变 | `appScreen` | **1** | 有 / 有 |
| `app_refresh` | 预置合法 token/user，打开 `#/app` 后 reload | `nova_token=valid-token`、`nova_user=alice`，不变 | `appScreen` | **1** | 有 / 有 |

模型中的 storage 不变来自既有 key 读取与生命周期控制流契约；不等同于真实 `localStorage` 读写观测。模型 app 入口包含 app shell、聊天欢迎内容、输入框、New chat 和 Recent/session 入口。

## 运行时边界

以下项目明确记录为 **unavailable**，没有伪造为通过：真实浏览器执行、真实 storage、computed `display/visibility/opacity`、paint/layout、console error、`window.onerror`、uncaught exception、`unhandledrejection`、资源错误、真实网络请求和 SSE。MiniDOM 只模拟 `setView("app")` 后的 class 控制流；Node `--check` 只做语法解析。

因此，本报告不能声称“真实刷新后无 console/uncaught exception”，只能确认静态契约与模型终态符合预期。需要浏览器或等价真实 DOM/runtime 后，才能完成该任务中运行时部分的最终验收。

## Diff boundary

本任务未修改 `static/index.html`、后端、Agent、prompts、测试或其他生产文件；新增证据与报告均位于 `.kiro/specs/nova-chat-interface-black-screen/`。完整结构化结果见 `task6-token-refresh-evidence.json`。

## Canonical source identity

Task 6 evidence records the current raw UTF-8 HTML SHA-256 `dc8969b4a7e92b30f8a95cfca1a9dbc6cfc2d44bb7ee71655dd596d3a0ec5130` and inline-script SHA-256 `78f5bab674e2235e01ab360a309a279d61063c3a6ccedb859793c0d67a432862`. The checker-native `6789b06…`/`5999838…` values are LF-normalized text hashes.