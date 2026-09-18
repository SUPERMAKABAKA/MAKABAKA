# Task 5 顶层视图互斥可见性回归报告

## 结果

**静态模型检查通过；真实 browser/computed CSS/paint/console/runtime blocked/unverified。** 基于修复后的 `static/index.html` 对六条路径执行了现有 `exploration_static_harness.py` 的 `MiniDOM` 生命周期模型检查。六条路径均得到模型终态 `visibleTopLevelViewCount = 1`，并且模型中的预期视图均有可见内容与交互入口。

这不是浏览器 smoke pass：harness 没有执行 inline JavaScript，也没有进行真实 DOM layout、computed style、paint、hit testing、storage/hash transition 或 console 捕获。

## 验证命令

- Visibility harness：调用 `exploration_static_harness.py` 的 `simulate_path()` 覆盖六条既定路径；dependency-free，完成。
- Node syntax：`C:\\Program Files\\nodejs\\node.exe --check .kiro/specs/nova-chat-interface-black-screen/task3-inline-script.js`
  - Node：`v24.19.0`
  - return code：`0`
  - stderr：空
- 生产文件：未由本任务修改。

## 六路径模型结果

| 路径 | 预期可见视图 | 模型可见顶层数量 | 内容 | 交互入口 | 运行时状态 |
|---|---|---:|---|---|---|
| `first_open` | `welcomeScreen` | **1** | 有 | 有 | blocked/unverified |
| `direct_auth_hash` | `authScreen` | **1** | 有 | 有 | blocked/unverified |
| `login_success` | `appScreen` | **1** | 有 | 有 | blocked/unverified |
| `existing_token_boot` | `appScreen` | **1** | 有 | 有 | blocked/unverified |
| `app_refresh` | `appScreen` | **1** | 有 | 有 | blocked/unverified |
| `logout_to_welcome` | `welcomeScreen` | **1** | 有 | 有 | blocked/unverified |

完整的 storage/hash 触发状态、三视图 class/display/visibility/opacity、交互入口计数和每条路径操作步骤见 `task5-visibility-evidence.json`。

## 运行时边界

以下项目没有被伪造为通过，均记录为 unavailable/unverified：真实浏览器执行、computed CSS visibility、paint/layout、console error、`window.onerror`、`unhandledrejection`、resource error、真实交互和网络/SSE。Node `--check` 只证明当前抽取 inline script 可被 Node 解析，不证明浏览器运行时无异常。

## 结论

任务 5 的 dependency-free 模型回归满足唯一可见顶层视图、内容和交互入口三项模型断言；Node 语法检查通过。由于真实 browser/runtime 不可用，本任务不能声称六条路径的真实 computed visibility 或 console/uncaught-exception 回归已验证。

## Canonical source identity

Task 5 evidence records the current raw UTF-8 HTML SHA-256 `dc8969b4a7e92b30f8a95cfca1a9dbc6cfc2d44bb7ee71655dd596d3a0ec5130` and inline-script SHA-256 `78f5bab674e2235e01ab360a309a279d61063c3a6ccedb859793c0d67a432862`. The checker-native `6789b06…`/`5999838…` values are LF-normalized text hashes.