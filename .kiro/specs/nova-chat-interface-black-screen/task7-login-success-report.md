# Task 7 登录成功进入 app 验证报告

## 结果
**静态 source-contract、MiniDOM control-flow、Node syntax 和 preservation contracts 通过；真实 auth/browser runtime unavailable。**

本任务没有发送真实认证请求、没有安装浏览器、没有执行 inline JavaScript，也没有修改 `static/index.html`。登录成功分支仅使用占位响应在 MiniDOM 中建模，不能替代真实登录成功证据。

## 验证命令
- 本任务检查：`python task7_login_success_check.py`；source-contract **22/22 PASS**。
- Node syntax：`["C:\\\\Program Files\\\\nodejs\\\\node.exe", "--check", "D:\\NUS\\Hackson\\MAKABAKA\\.kiro\\specs\\nova-chat-interface-black-screen\\task7-login-success-inline-script.js"]`；Node `v24.19.0`；return code `0`；stderr `(none)`。
- Preservation：`python .kiro\specs\nova-chat-interface-black-screen\task3_preservation_check.py`；结果 **PASS**，静态 contracts **58/58**，protected structure **PASS**。
- 浏览器交互、真实 `/auth/login` 请求、console/uncaught/computed visibility：**unavailable**。

## 认证成功 source-contract

- `auth submit handler exists`: **PASS** (lines [1])
- `auth request uses dynamic endpoint and POST`: **PASS** (lines [8])
- `auth request sends JSON content type`: **PASS** (lines [8])
- `auth request payload is username/password`: **PASS** (lines [9])
- `2xx gate rejects non-ok responses before success`: **PASS** (lines [11])
- `successful response assigns token and username`: **PASS** (lines [12])
- `successful response writes nova_token`: **PASS** (lines [13])
- `successful response writes nova_user`: **PASS** (lines [13])
- `successful response awaits authSucceeded`: **PASS** (lines [14])
- `network error keeps existing error message`: **PASS** (lines [15])
- `finally restores auth submit state`: **PASS** (lines [19])
- `authSucceeded calls enterApp`: **PASS** (lines [9])
- `enterApp calls setView app`: **PASS** (lines [2])
- `enterApp restores app input focus`: **PASS** (lines [7])
- `setView excludes welcome when app selected`: **PASS** (lines [4])
- `setView excludes auth when app selected`: **PASS** (lines [5])
- `setView excludes app when another view selected`: **PASS** (lines [6])
- `app chat input exists`: **PASS** (lines [1163])
- `new chat session entry exists`: **PASS** (lines [1131])
- `recent session entry exists`: **PASS** (lines [1132])
- `history session list exists`: **PASS** (lines [1171])
- `success effects occur only after 2xx guard and in existing order`: **PASS** (positions {'if(!res.ok){': 519, 'token=data.token; username=data.username;': 591, 'localStorage.setItem("nova_token",token)': 637, 'localStorage.setItem("nova_user",username)': 679, 'await authSucceeded();': 727})

关键顺序已静态确认：`!res.ok` 错误返回 → `token=data.token`/`username=data.username` → 两个既有 localStorage 写入 → `await authSucceeded()`。因此没有把非 2xx 响应或本地占位数据当成成功。

## MiniDOM 登录成功 control-flow

- 初始路径：模型切换到 `authScreen`；模型不发请求、不使用真实凭据。
- 成功响应模型：仅在 `ok=true` 的占位响应下写入 `nova_token`/`nova_user`，然后模拟 `authSucceeded()` → `enterApp()` → `setView("app")`。
- 最终 visible top-level count：**1**；visible view：`appScreen`。
- app 可见内容：**True**；交互内容（input/session entries）：**True**。
- 非 2xx guard 模型：storage unchanged **True**；未进入 app **True**；auth error/finally 语义仅做源码和控制流保留检查。

## Preservation contracts

现有 preservation 检查静态结果为 **58/58**，并保留认证、welcome/auth routing、chat/SSE、session/recommendation contracts。其 runtime 字段仍为 `blocked_unavailable`，不作为真实运行时通过。

## Runtime boundary

以下项目明确为 **unavailable**，没有伪造为通过：真实 `/auth/login` 或 `/auth/register` 请求、真实 token/username storage 读写、真实 browser interaction、computed `display/visibility/opacity`、paint/layout/hit testing、console error、`window.onerror`、uncaught exception、unhandled rejection、resource error、真实网络和 SSE。Node `--check` 仅证明抽取脚本可解析；MiniDOM 仅证明观察到的控制流模型具有唯一 app 终态。

## Diff boundary

- 当前 `static/index.html` SHA-256：`c7fe9d9b59ccc1b168fe6bef12383bd89b70f08b09f5215e6fbd8e57bc9ca2d4`。
- 与任务 6 source SHA 一致：**False**。
- 工作树 `git diff --name-only`：`.kiro/specs/nova-chat-interface-redesign/tasks.md, static/index.html`；这些是观察到的现有 diff，不归因于任务 7。
- 本任务生产修改：**none**；新增内容仅位于 `.kiro/specs/nova-chat-interface-black-screen/`。

## 结论

任务 7 的静态验证完成：认证成功判定仍由真实 `res.ok` 分支控制，既有 storage key 和错误/finally 语义未被替换，成功控制流模型最终唯一显示 `appScreen` 且包含聊天 input、New chat 和 Recent/session 入口。真实登录和浏览器可见性需在可用 browser/runtime 后补做，当前不声称 browser smoke pass。
