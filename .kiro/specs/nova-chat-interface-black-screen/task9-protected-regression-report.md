# Task 9 受保护 welcome/auth 页面回归报告

## 结果
- HTML/source-contract：**PASS**（27/27）。
- Node `--check`：**PASS**；Node `v24.19.0`。
- 生产代码：**未修改**；检查器、证据和报告均位于本 bugfix spec 目录。
- 真实视觉像素、浏览器交互、computed CSS、console、uncaught exception：**unavailable**（未安装/使用浏览器）。

## 覆盖范围

- welcome 首屏、`Start`、`Sign in` 入口及 `#/auth` 路由 source contract。
- auth `Sign in`/`Create account` 切换、密码显示/隐藏、用户名/密码校验、认证失败提示、认证 API、loading/finally、`Back to home`。
- `nova_token`/`nova_user` 读取与写入、`/auth/{login|register}` POST、JSON payload、错误 fallback 与原 task 3 baseline 完整 source hash 对照。
- welcome/auth DOM/CSS 保护边界、初始 hidden 规则及必要控件存在性。

## Node syntax evidence

- Command: `["C:\\\\Program Files\\\\nodejs\\\\node.exe", "--check", "D:\\NUS\\Hackson\\MAKABAKA\\.kiro\\specs\\nova-chat-interface-black-screen\\task9-protected-regression-inline-script.js"]`
- Return code: `0`
- stderr: `(none)`

## Source-contract checks

- `welcome/auth required ids present`: **PASS** — authBack, authErr, authForm, authScreen, authSubmit, password, pwToggle, tabLogin, tabRegister, username, welcomeScreen, wpSignIn, wpStart
- `welcome starts hidden`: **PASS** — welcomeScreen has initial hidden class
- `welcome first-screen content preserved`: **PASS** — headline and Start control
- `welcome Sign in control preserved`: **PASS** — wpSignIn text and button semantics
- `welcome Start and Sign in route to auth`: **PASS** — both controls use the existing openAuth handler
- `openAuth preserves auth hash route`: **PASS** — pushState to #/auth
- `openAuth preserves auth view transition`: **PASS** — openAuth calls setView("auth")
- `direct auth hash is honored`: **PASS** — boot hash branch
- `auth form and error region preserved`: **PASS** — authForm and role=alert region
- `auth mode tabs preserved`: **PASS** — Sign in/Create account controls
- `auth mode switching semantics preserved`: **PASS** — existing setMode handlers
- `setMode preserves labels and password guidance`: **PASS** — submit labels, placeholder, and mode-dependent password guidance
- `password visibility control preserved`: **PASS** — type and accessible label toggle
- `password toggle remains wired`: **PASS** — pwToggle click handler
- `auth validation errors preserved`: **PASS** — username/password validation messages
- `auth API endpoint and method preserved`: **PASS** — POST /auth/login or /auth/register
- `auth JSON payload and content type preserved`: **PASS** — JSON headers and username/password payload
- `auth success storage semantics preserved`: **PASS** — token/username assignment and keys
- `auth failure error fallback preserved`: **PASS** — server error message fallback
- `auth network error handling preserved`: **PASS** — network error message
- `auth finally loading reset preserved`: **PASS** — finally restores button state and label
- `Back to home control preserved`: **PASS** — authBack text and button
- `Back to home route semantics preserved`: **PASS** — authBack handler and history/enterWelcome behavior
- `welcome/auth CSS scope preserved`: **PASS** — front-of-house CSS selectors remain present
- `hidden rule preserved`: **PASS** — hidden keeps display:none!important
- `task3 full source baseline unchanged`: **PASS** — current=c7fe9d9b59ccc1b168fe6bef12383bd89b70f08b09f5215e6fbd8e57bc9ca2d4, task3=c7fe9d9b59ccc1b168fe6bef12383bd89b70f08b09f5215e6fbd8e57bc9ca2d4
- `task3 inline script baseline unchanged`: **PASS** — current=591d2919704f3b1154441f8790bc881bd8052bd8c5119f119a9c85f5fe33e6f4, task3=591d2919704f3b1154441f8790bc881bd8052bd8c5119f119a9c85f5fe33e6f4

## Baseline and boundary

- Current `static/index.html` SHA-256: `c7fe9d9b59ccc1b168fe6bef12383bd89b70f08b09f5215e6fbd8e57bc9ca2d4`.
- Task 3 baseline SHA-256: `c7fe9d9b59ccc1b168fe6bef12383bd89b70f08b09f5215e6fbd8e57bc9ca2d4`; exact match: **True**.
- Current inline script SHA-256: `591d2919704f3b1154441f8790bc881bd8052bd8c5119f119a9c85f5fe33e6f4`.
- Task 3 inline script SHA-256: `591d2919704f3b1154441f8790bc881bd8052bd8c5119f119a9c85f5fe33e6f4`; exact match: **True**.
- Task 9 production diff attribution: **none**. No write operation targeted `static/index.html`.
- Hash equality is source-level preservation evidence; it does not prove runtime rendering or browser interaction.

## Runtime boundary

The following are deliberately not claimed as passing: real welcome/auth pixels, focus and hit testing, computed `display`/`visibility`/`opacity`, browser tab/password interaction, real authentication requests and storage mutation, console errors, `window.onerror`, uncaught exceptions, unhandled rejections, resource failures, and network timing. They remain **unavailable** because no browser was installed or used.

## Conclusion

Task 9 source-level regression checks **pass**. The protected welcome/auth source matches task 3 exactly, and Node syntax parsing passes. This is not a browser/runtime sign-off; task 9's real visual and interaction criteria remain unavailable.
