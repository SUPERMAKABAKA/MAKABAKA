# Task 8 刷新与登出回 welcome 生命周期验证报告

## 结果
**静态 source-contract 与 MiniDOM 模型通过；真实 refresh/logout/browser/runtime unavailable。** 本任务没有修改 `static/index.html` 或其他生产代码。模型证据不被标记为真实浏览器通过。

## 验证命令
- Node syntax：`node --check task8-inline-script.tmp.js`，结果 **PASS**，Node `v24.19.0`，return code `0`。临时脚本已删除。
- Preservation：复用 `task3_preservation_check.py`，结果 **PASS**；其 runtime boundary 仍为 **unavailable**。
- MiniDOM：模型执行 `app_refresh` 与 `logout_to_welcome`；未执行 inline JavaScript，未使用浏览器或真实 storage。

## Source-contract 结果

共 17 项，全部 **PASS**。覆盖 token/user 读取、authenticated boot → `enterApp()` → `setView("app")`、精确互斥 hidden 切换、logout storage/session/history/hash 清理、`enterWelcome()` → `setView("welcome")` 及 app 交互入口。

## app refresh 模型

- 初始：`nova_token=valid-token`、`nova_user=alice`，hash `#/app`。
- 模拟 reload boot：调用既有 `enterApp()` 控制流。
- 模型最终视图：唯一 `appScreen`；模型内容/交互：有。
- 模型 storage：两个 key/value 不变。
- 说明：`hiddenClassModel`/`displayModel` 仅表示生命周期 class 控制流，不是 computed CSS/layout 观测。

## logout 模型

- 模拟 Sign out：移除 `nova_token` 与 `nova_user`；清空 `streamInner` 并恢复 welcome；清空 `sessions`、`histEl`，生成新 `sessionId`；更新 URL 到无 hash；调用 `enterWelcome()`，再由 `setView("welcome")` 互斥显示 welcome。
- 模型最终视图：唯一 `welcomeScreen`；模型内容/交互：有。
- 模型最终 storage：空；sessions/history：空；hash：空。

## Runtime boundary

以下全部保持 **unavailable**，没有伪造通过：真实 refresh、真实 logout、浏览器 computed `display/visibility/opacity`、paint/hit testing、console error、`window.onerror`、uncaught exception、unhandled rejection、resource error、network 与 SSE。Node `--check` 仅证明抽取脚本可解析；preservation 与 MiniDOM 仅为静态/模型证据。

## Diff boundary

- 生产修改：无。
- 只生成：`task8-lifecycle-evidence.json`、`task8-lifecycle-report.md`。
- 一次性检查器及抽取脚本已在完成后删除。

结构化结果见 `task8-lifecycle-evidence.json`。

## Canonical source identity

Task 8 evidence records the current raw UTF-8 HTML SHA-256 `dc8969b4a7e92b30f8a95cfca1a9dbc6cfc2d44bb7ee71655dd596d3a0ec5130` and inline-script SHA-256 `78f5bab674e2235e01ab360a309a279d61063c3a6ccedb859793c0d67a432862`. The checker-native `6789b06…`/`5999838…` values are LF-normalized text hashes.