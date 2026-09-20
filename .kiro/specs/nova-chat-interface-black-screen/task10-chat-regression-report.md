# Task 10 app chat/session/SSE 与受保护 payload 回归报告

## 结果
- 总体 source/model regression：**PASS**。
- 复用 task 3 preservation source contracts：**58/58 PASS**。
- 复用 task 3 protected structure：**5/5 PASS**。
- Node `--check`：**PASS**（v24.19.0）。
- task 10 focused chat/session/SSE/payload model checks：**35/35 PASS**。
- 生产代码：**未修改**；本检查器只生成 bugfix spec 目录内的证据文件。
- 真实 chat request、SSE exchange、session UI、recommendation UI、network、console：**unavailable**；未伪造 runtime pass。

## 覆盖的 source/model contracts

### Chat transport and fallback
- `POST /chat/stream`。
- `Content-Type: application/json`、条件式 `Authorization: Bearer <token>`。
- `session_id`/`message` JSON payload。
- non-OK/missing body fallback、network catch fallback，以及 finally 中的 busy/send/session 保存生命周期。

### SSE
- `event:`/`data:` 行解析、空行分帧、JSON decode fallback。
- `token`、`recommendations`、`error` 三类事件分支及其渲染/数据保留行为。

### Session lifecycle
- `sessions` keyed by `sessionId`、`saveSession` innerHTML snapshot。
- `pushHistory` 创建会话、`switchToSession` 恢复会话、`resetChat` 新建会话并恢复 welcome。
- history click switching 与新 session 的 history entry。

### Recommendation payload and product selection
- recommendation group payload preservation、title/product fallback、reason、positives/negatives、rank formatting、insufficient notice。
- delegated card selection、`openRecommendationsPanel`、`selectProduct`、`closeProduct`。
- AliExpress iframe URL 与 Amazon external search URL。

## Focused model checks

- `chat endpoint is POST /chat/stream`: **PASS**
- `chat request declares JSON content type`: **PASS**
- `chat request conditionally sends bearer token`: **PASS**
- `chat request sends session_id and message`: **PASS**
- `non-ok or missing body uses request fallback`: **PASS**
- `request fallback preserves failure copy`: **PASS**
- `network catch preserves network fallback`: **PASS**
- `send lifecycle resets busy and send state`: **PASS**
- `SSE parser reads event lines`: **PASS**
- `SSE parser reads data lines`: **PASS**
- `SSE parser JSON-decodes data`: **PASS**
- `SSE token event appends token text`: **PASS**
- `SSE recommendations event retains response data`: **PASS**
- `SSE error event appends error text`: **PASS**
- `SSE stream is split on blank event frames`: **PASS**
- `session store is keyed by sessionId`: **PASS**
- `saveSession stores stream innerHTML`: **PASS**
- `pushHistory creates session snapshot`: **PASS**
- `switchToSession restores session snapshot`: **PASS**
- `resetChat creates new session and restores welcome`: **PASS**
- `history click switches selected session`: **PASS**
- `send creates history entry for a new session`: **PASS**
- `recommendation payload is retained by group`: **PASS**
- `recommendation title and product fallback render`: **PASS**
- `recommendation reason is escaped and rendered`: **PASS**
- `recommendation positives and negatives are bounded`: **PASS**
- `recommendation rank is derived from display index`: **PASS**
- `insufficient recommendation status keeps notice`: **PASS**
- `recommendation click resolves payload and index`: **PASS**
- `recommendation click opens panel and selects product`: **PASS**
- `product panel maps recommendation titles and queries`: **PASS**
- `AliExpress embed URL is preserved`: **PASS**
- `Amazon external search URL is preserved`: **PASS**
- `selectProduct sets iframe and external link`: **PASS**
- `closeProduct clears panel and iframe`: **PASS**

## Reused task 3 evidence

- Task 3 evidence file: `task3-preservation-evidence.json`。
- Task 3 static contracts: **58/58**。
- Task 3 protected structure: **5/5**。
- Task 3 recorded Node syntax: **PASS**。
- Task 3 runtime status is not treated as a pass; browser/runtime remains unavailable for this task.

## Source and boundary evidence

- Current `static/index.html` SHA-256: `c7fe9d9b59ccc1b168fe6bef12383bd89b70f08b09f5215e6fbd8e57bc9ca2d4`。
- Task 3 baseline SHA-256: `c7fe9d9b59ccc1b168fe6bef12383bd89b70f08b09f5215e6fbd8e57bc9ca2d4`；exact match: **True**。
- Current inline script SHA-256: `591d2919704f3b1154441f8790bc881bd8052bd8c5119f119a9c85f5fe33e6f4`。
- Task 3 inline script SHA-256: `591d2919704f3b1154441f8790bc881bd8052bd8c5119f119a9c85f5fe33e6f4`；exact match: **True**。
- Observed `git diff --name-only`: `.kiro/specs/nova-chat-interface-redesign/tasks.md, static/index.html`。
- Task 10 wrote no production file and made no request to modify `static/index.html`。

## Runtime boundary

以下项目明确为 **unavailable**，不能由本 source/model check 推断为通过：真实 `/chat/stream` request/header/payload、SSE token/recommendations/error exchange、session 新建/切换/reset UI、推荐 card 点击与 product panel、network timing、console error、uncaught exception、unhandled rejection、computed visibility 和 browser hit testing。

## Conclusion

Task 10 的静态/模型检查通过；该结论不等同于浏览器 runtime sign-off。
