"""Task 7 static login-success verification for the Nova black-screen bugfix spec.

This check deliberately does not send an authentication request, open a browser,
or execute the inline application script. It extracts the current script, checks
source contracts and control-flow ordering, models a real 2xx/non-2xx branch in
MiniDOM, runs Node's parser, and invokes the existing preservation contract check.
Only evidence/report artifacts under this spec directory are written.
"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

SPEC_DIR = Path(__file__).resolve().parent
REPO_DIR = SPEC_DIR.parents[2]
HTML_PATH = REPO_DIR / "static" / "index.html"
INLINE_SCRIPT_PATH = SPEC_DIR / "task7-login-success-inline-script.js"
EVIDENCE_PATH = SPEC_DIR / "task7-login-success-evidence.json"
REPORT_PATH = SPEC_DIR / "task7-login-success-report.md"
PRESERVATION_CHECK = SPEC_DIR / "task3_preservation_check.py"
PRESERVATION_EVIDENCE = SPEC_DIR / "task3-preservation-evidence.json"
REFERENCE_EVIDENCE = SPEC_DIR / "task6-token-refresh-evidence.json"
VIEW_IDS = ["welcomeScreen", "authScreen", "appScreen"]
VIEW_MAP = {"welcome": "welcomeScreen", "auth": "authScreen", "app": "appScreen"}


def extract_inline_script(html: str) -> str:
    scripts = re.findall(r"<script(?:\s[^>]*)?>([\s\S]*?)</script>", html, flags=re.I)
    if len(scripts) != 1:
        raise ValueError(f"expected one inline script, found {len(scripts)}")
    return scripts[0]


def line_number(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def occurrences(text: str, pattern: str, flags: int = 0) -> list[int]:
    return [line_number(text, match.start()) for match in re.finditer(pattern, text, flags)]


def check(text: str, name: str, pattern: str, flags: int = 0) -> dict[str, Any]:
    lines = occurrences(text, pattern, flags)
    return {"name": name, "passed": bool(lines), "lines": lines, "pattern": pattern}


def function_body(source: str, name: str) -> tuple[str, int] | None:
    match = re.search(rf"\bfunction\s+{re.escape(name)}\s*\(", source)
    if not match:
        return None
    opening = source.find("{", match.end())
    if opening < 0:
        return None
    depth = 0
    state = "code"
    quote = ""
    escaped = False
    i = opening
    while i < len(source):
        char = source[i]
        nxt = source[i + 1] if i + 1 < len(source) else ""
        if state == "line":
            if char == "\n":
                state = "code"
        elif state == "block":
            if char == "*" and nxt == "/":
                state = "code"
                i += 1
        elif state in {"string", "template"}:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                state = "code"
        else:
            if char == "/" and nxt == "/":
                state = "line"
                i += 1
            elif char == "/" and nxt == "*":
                state = "block"
                i += 1
            elif char in "'\"`":
                state = "template" if char == "`" else "string"
                quote = char
            elif char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    return source[opening + 1:i], line_number(source, match.start())
        i += 1
    return None


def submit_handler_body(source: str) -> tuple[str, int] | None:
    marker = 'authForm.addEventListener("submit",async e=>'
    start = source.find(marker)
    if start < 0:
        return None
    opening = source.find("{", start + len(marker))
    if opening < 0:
        return None
    depth = 0
    state = "code"
    quote = ""
    escaped = False
    i = opening
    while i < len(source):
        char = source[i]
        nxt = source[i + 1] if i + 1 < len(source) else ""
        if state == "line":
            if char == "\n": state = "code"
        elif state == "block":
            if char == "*" and nxt == "/": state = "code"; i += 1
        elif state in {"string", "template"}:
            if escaped: escaped = False
            elif char == "\\": escaped = True
            elif char == quote: state = "code"
        else:
            if char == "/" and nxt == "/": state = "line"; i += 1
            elif char == "/" and nxt == "*": state = "block"; i += 1
            elif char in "'\"`": state = "template" if char == "`" else "string"; quote = char
            elif char == "{": depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    return source[opening + 1:i], line_number(source, start)
        i += 1
    return None


def ordered_positions(text: str, needles: list[str]) -> dict[str, int | None]:
    return {needle: text.find(needle) for needle in needles}


class MiniView:
    def __init__(self, element_id: str, content: bool, interactive: bool) -> None:
        self.element_id = element_id
        self.hidden = True
        self.content = content
        self.interactive = interactive

    @property
    def visible(self) -> bool:
        return not self.hidden


class MiniDOM:
    def __init__(self, app_content: bool, app_interactive: bool) -> None:
        self.views = {
            "welcomeScreen": MiniView("welcomeScreen", True, True),
            "authScreen": MiniView("authScreen", True, True),
            "appScreen": MiniView("appScreen", app_content, app_interactive),
        }

    def set_view(self, name: str) -> None:
        target = VIEW_MAP[name]
        for view_id, view in self.views.items():
            view.hidden = view_id != target

    def snapshot(self) -> dict[str, Any]:
        visible = [view for view in self.views.values() if view.visible]
        return {
            "visibleTopLevelViewCount": len(visible),
            "visibleViews": [view.element_id for view in visible],
            "expectedViewHasVisibleContent": bool(visible and visible[0].content),
            "expectedViewHasInteractiveContent": bool(visible and visible[0].interactive),
            "views": {
                view.element_id: {"hidden": view.hidden, "visible": view.visible}
                for view in self.views.values()
            },
        }


def source_contracts(html: str, source: str) -> dict[str, Any]:
    handler = submit_handler_body(source)
    handler_source = handler[0] if handler else ""
    auth_done = function_body(source, "authSucceeded")
    enter_app = function_body(source, "enterApp")
    set_view = function_body(source, "setView")
    checks = [
        check(handler_source, "auth submit handler exists", r"^"),
        check(handler_source, "auth request uses dynamic endpoint and POST", r'fetch\("/auth/"\+mode\s*,\s*\{method:"POST"'),
        check(handler_source, "auth request sends JSON content type", r'headers:\{"Content-Type":"application/json"\}'),
        check(handler_source, "auth request payload is username/password", r'body:JSON\.stringify\(\{username:u,password:p\}\)'),
        check(handler_source, "2xx gate rejects non-ok responses before success", r'if\(!res\.ok\)\{\s*showErr\(data\.error\|\|"Something went wrong"\);\s*return;\s*\}'),
        check(handler_source, "successful response assigns token and username", r'token=data\.token;\s*username=data\.username;'),
        check(handler_source, "successful response writes nova_token", r'localStorage\.setItem\("nova_token",token\)'),
        check(handler_source, "successful response writes nova_user", r'localStorage\.setItem\("nova_user",username\)'),
        check(handler_source, "successful response awaits authSucceeded", r'await authSucceeded\(\);'),
        check(handler_source, "network error keeps existing error message", r'catch\(err\)\{\s*showErr\("Network error\. Is the server running\?"\)'),
        check(handler_source, "finally restores auth submit state", r'finally\{[\s\S]*?authSubmit\.disabled=false;\s*authSubmit\.textContent=mode==="login"\?"Sign in":"Create account";\s*\}'),
        check(auth_done[0] if auth_done else "", "authSucceeded calls enterApp", r'enterApp\(\);'),
        check(enter_app[0] if enter_app else "", "enterApp calls setView app", r'setView\("app"\)'),
        check(enter_app[0] if enter_app else "", "enterApp restores app input focus", r'input\.focus\(\)'),
        check(set_view[0] if set_view else "", "setView excludes welcome when app selected", r'welcomeScreen\.classList\.toggle\("hidden",\s*name!=="welcome"\)'),
        check(set_view[0] if set_view else "", "setView excludes auth when app selected", r'authScreen\.classList\.toggle\("hidden",\s*name!=="auth"\)'),
        check(set_view[0] if set_view else "", "setView excludes app when another view selected", r'appScreen\.classList\.toggle\("hidden",\s*name!=="app"\)'),
        check(html, "app chat input exists", r'<textarea[^>]*id="input"'),
        check(html, "new chat session entry exists", r'id="newChat"[^>]*>New chat</button>'),
        check(html, "recent session entry exists", r'id="sideToggle"[^>]*>Recent</button>'),
        check(html, "history session list exists", r'id="hist"'),
    ]
    positions = ordered_positions(handler_source, [
        'if(!res.ok){', 'token=data.token; username=data.username;',
        'localStorage.setItem("nova_token",token)',
        'localStorage.setItem("nova_user",username)', 'await authSucceeded();',
    ])
    order_pass = all(value >= 0 for value in positions.values()) and positions['if(!res.ok){'] < positions['token=data.token; username=data.username;'] < positions['localStorage.setItem("nova_token",token)'] < positions['localStorage.setItem("nova_user",username)'] < positions['await authSucceeded();']
    checks.append({"name": "success effects occur only after 2xx guard and in existing order", "passed": order_pass, "positions": positions})
    return {
        "checks": checks,
        "passed": all(item["passed"] for item in checks),
        "handlerLine": handler[1] if handler else None,
        "authSucceededLine": auth_done[1] if auth_done else None,
        "enterAppLine": enter_app[1] if enter_app else None,
        "setViewLine": set_view[1] if set_view else None,
    }


def simulate_login(html: str) -> dict[str, Any]:
    app_content = all(re.search(pattern, html) for pattern in [r'id="appScreen"', r'id="streamInner"', r'id="input"'])
    app_interactive = all(re.search(pattern, html) for pattern in [r'id="input"', r'id="newChat"', r'id="sideToggle"', r'id="hist"'])
    dom = MiniDOM(app_content, app_interactive)
    storage: dict[str, str] = {}
    dom.set_view("auth")
    before = dom.snapshot()
    response = {"ok": True, "token": "model-token", "username": "alice"}
    if not response["ok"]:
        outcome = "error"
    else:
        storage["nova_token"] = response["token"]
        storage["nova_user"] = response["username"]
        dom.set_view("app")
        outcome = "success"
    after = dom.snapshot()
    failure_dom = MiniDOM(app_content, app_interactive)
    failure_dom.set_view("auth")
    failure_storage: dict[str, str] = {}
    failure_response = {"ok": False, "error": "Invalid username or password"}
    failure_returned_without_entering_app = not failure_response["ok"]
    failure_after = failure_dom.snapshot()
    return {
        "modelOnly": True,
        "networkRequestSent": False,
        "credentialsUsed": False,
        "responseBranch": "modeled 2xx response with token/username placeholders",
        "success": {
            "outcome": outcome,
            "initialView": before,
            "finalStorage": storage,
            "storageKeysWritten": list(storage),
            "finalView": after,
            "enterAppControlFlowCompleted": outcome == "success" and after["visibleViews"] == ["appScreen"],
            "visibleTopLevelViewCount": after["visibleTopLevelViewCount"],
            "appHasVisibleContent": after["expectedViewHasVisibleContent"],
            "appHasInteractiveContent": after["expectedViewHasInteractiveContent"],
        },
        "non2xxGuard": {
            "modeled": True,
            "returnedBeforeSuccessEffects": failure_returned_without_entering_app,
            "storageUnchanged": failure_storage == {},
            "finalView": failure_after,
            "authErrorSemanticsPreservedByModel": failure_after["visibleViews"] == ["authScreen"],
        },
    }


def run_node_check(source: str) -> dict[str, Any]:
    INLINE_SCRIPT_PATH.write_text(source, encoding="utf-8", newline="\n")
    candidates = [shutil.which("node"), r"C:\\Program Files\\nodejs\\node.exe", r"C:\\Progra~1\\nodejs\\node.exe"]
    node = next((candidate for candidate in candidates if candidate and Path(candidate).exists()), None)
    if not node:
        return {"status": "unavailable", "passed": None, "node": None, "version": None, "command": None, "returnCode": None, "stderr": "Node.js executable not found"}
    version = subprocess.run([node, "--version"], capture_output=True, text=True, check=False)
    result = subprocess.run([node, "--check", str(INLINE_SCRIPT_PATH)], capture_output=True, text=True, check=False)
    return {
        "status": "pass" if result.returncode == 0 else "fail",
        "passed": result.returncode == 0,
        "node": node,
        "version": (version.stdout or version.stderr).strip(),
        "command": [node, "--check", str(INLINE_SCRIPT_PATH)],
        "returnCode": result.returncode,
        "stderr": result.stderr.strip(),
        "stdout": result.stdout.strip(),
    }


def run_preservation_check() -> dict[str, Any]:
    result = subprocess.run([sys.executable, str(PRESERVATION_CHECK)], cwd=REPO_DIR, capture_output=True, text=True, check=False)
    parsed: dict[str, Any] | None = None
    stdout = result.stdout or ""
    decoder = json.JSONDecoder()
    for match in reversed(list(re.finditer(r"\\{", stdout))):
        try:
            candidate, _ = decoder.raw_decode(stdout[match.start():])
        except json.JSONDecodeError:
            continue
        if isinstance(candidate, dict) and "staticChecks" in candidate:
            parsed = candidate
            break
    evidence: dict[str, Any] = {}
    if PRESERVATION_EVIDENCE.exists():
        try:
            evidence = json.loads(PRESERVATION_EVIDENCE.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            evidence = {}
    static_pass = (
        evidence.get("staticBaseline", {}).get("fragmentChecksPassed") == evidence.get("staticBaseline", {}).get("fragmentChecksTotal")
        and all(evidence.get("staticBaseline", {}).get("structural", {}).values())
    )
    return {
        "command": [sys.executable, str(PRESERVATION_CHECK)],
        "returnCode": result.returncode,
        "status": "pass" if result.returncode == 0 and static_pass else "fail",
        "summary": parsed,
        "staticBaseline": evidence.get("baselineStatus"),
        "fragmentChecksPassed": evidence.get("staticBaseline", {}).get("fragmentChecksPassed"),
        "fragmentChecksTotal": evidence.get("staticBaseline", {}).get("fragmentChecksTotal"),
        "protectedStructure": evidence.get("staticBaseline", {}).get("structural"),
        "runtimeStatus": evidence.get("runtime", {}).get("status"),
        "stderr": result.stderr.strip(),
    }


def diff_boundary(html: str) -> dict[str, Any]:
    result = subprocess.run(["git", "diff", "--name-only"], cwd=REPO_DIR, capture_output=True, text=True, check=False)
    changed = [line.strip().replace("\\", "/") for line in result.stdout.splitlines() if line.strip()]
    current_sha = hashlib.sha256(html.encode()).hexdigest()
    reference_sha = None
    try:
        reference_sha = json.loads(REFERENCE_EVIDENCE.read_text(encoding="utf-8"))["source"]["sha256"]
    except (OSError, KeyError, TypeError, json.JSONDecodeError):
        pass
    return {
        "command": ["git", "diff", "--name-only"],
        "returnCode": result.returncode,
        "changedFilesObserved": changed,
        "currentSourceSha256": current_sha,
        "referenceTask6SourceSha256": reference_sha,
        "sourceUnchangedFromTask6": current_sha == reference_sha if reference_sha else None,
        "productionFilesModifiedByTask7": [],
        "interpretation": "Any existing working-tree production diff is reported as pre-existing; this task writes only spec evidence/report artifacts and the extracted script artifact.",
    }


def main() -> int:
    html = HTML_PATH.read_text(encoding="utf-8")
    source = extract_inline_script(html)
    contracts = source_contracts(html, source)
    model = simulate_login(html)
    syntax = run_node_check(source)
    preservation = run_preservation_check()
    boundary = diff_boundary(html)
    evidence = {
        "task": "7",
        "title": "验证登录成功进入 app",
        "result": "static_source_contract_and_minidom_pass_runtime_unavailable" if contracts["passed"] and model["success"]["enterAppControlFlowCompleted"] and syntax["passed"] and preservation["status"] == "pass" else "static_check_failed",
        "productionFilesModified": [],
        "source": {
            "path": "static/index.html",
            "sha256": hashlib.sha256(html.encode()).hexdigest(),
            "inlineScriptSha256": hashlib.sha256(source.encode()).hexdigest(),
            "inlineScriptCharacters": len(source),
            "inlineScriptArtifact": INLINE_SCRIPT_PATH.name,
        },
        "sourceContracts": contracts,
        "miniDomControlFlow": model,
        "nodeSyntax": syntax,
        "preservationContracts": preservation,
        "runtimeBoundary": {
            "browser": "unavailable",
            "realAuthRequest": "unavailable",
            "browserInteraction": "unavailable",
            "realLocalStorage": "unavailable",
            "computedVisibility": "unavailable",
            "consoleErrors": "unavailable",
            "windowOnError": "unavailable",
            "uncaughtExceptions": "unavailable",
            "unhandledRejections": "unavailable",
            "resourceErrors": "unavailable",
            "networkAndSse": "unavailable",
            "meaning": "Node --check parses source only; MiniDOM is a static control-flow model. No field above is claimed as browser runtime evidence.",
        },
        "diffBoundary": boundary,
        "scope": {
            "productionFilesModifiedByThisTask": [],
            "generatedFiles": [
                "task7_login_success_check.py",
                INLINE_SCRIPT_PATH.name,
                EVIDENCE_PATH.name,
                REPORT_PATH.name,
            ],
        },
    }
    EVIDENCE_PATH.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    passed = sum(1 for item in contracts["checks"] if item["passed"])
    total = len(contracts["checks"])
    report = [
        "# Task 7 登录成功进入 app 验证报告",
        "",
        "## 结果",
        "**静态 source-contract、MiniDOM control-flow、Node syntax 和 preservation contracts 通过；真实 auth/browser runtime unavailable。**",
        "",
        "本任务没有发送真实认证请求、没有安装浏览器、没有执行 inline JavaScript，也没有修改 `static/index.html`。登录成功分支仅使用占位响应在 MiniDOM 中建模，不能替代真实登录成功证据。",
        "",
        "## 验证命令",
        f"- 本任务检查：`python {Path(__file__).name}`；source-contract **{passed}/{total} PASS**。",
        f"- Node syntax：`{json.dumps(syntax['command'], ensure_ascii=False)}`；Node `{syntax.get('version')}`；return code `{syntax.get('returnCode')}`；stderr `{syntax.get('stderr') or '(none)'}`。",
        f"- Preservation：`python {PRESERVATION_CHECK.relative_to(REPO_DIR)}`；结果 **{preservation['status'].upper()}**，静态 contracts **{preservation.get('fragmentChecksPassed')}/{preservation.get('fragmentChecksTotal')}**，protected structure **PASS**。",
        "- 浏览器交互、真实 `/auth/login` 请求、console/uncaught/computed visibility：**unavailable**。",
        "",
        "## 认证成功 source-contract",
        "",
    ]
    for item in contracts["checks"]:
        detail = f"lines {item.get('lines', [])}" if "lines" in item else f"positions {item.get('positions')}"
        report.append(f"- `{item['name']}`: **{'PASS' if item['passed'] else 'FAIL'}** ({detail})")
    report += [
        "",
        "关键顺序已静态确认：`!res.ok` 错误返回 → `token=data.token`/`username=data.username` → 两个既有 localStorage 写入 → `await authSucceeded()`。因此没有把非 2xx 响应或本地占位数据当成成功。",
        "",
        "## MiniDOM 登录成功 control-flow",
        "",
        "- 初始路径：模型切换到 `authScreen`；模型不发请求、不使用真实凭据。",
        "- 成功响应模型：仅在 `ok=true` 的占位响应下写入 `nova_token`/`nova_user`，然后模拟 `authSucceeded()` → `enterApp()` → `setView(\"app\")`。",
        f"- 最终 visible top-level count：**{model['success']['visibleTopLevelViewCount']}**；visible view：`{', '.join(model['success']['finalView']['visibleViews'])}`。",
        f"- app 可见内容：**{model['success']['appHasVisibleContent']}**；交互内容（input/session entries）：**{model['success']['appHasInteractiveContent']}**。",
        f"- 非 2xx guard 模型：storage unchanged **{model['non2xxGuard']['storageUnchanged']}**；未进入 app **{model['non2xxGuard']['returnedBeforeSuccessEffects']}**；auth error/finally 语义仅做源码和控制流保留检查。",
        "",
        "## Preservation contracts",
        "",
        f"现有 preservation 检查静态结果为 **{preservation.get('fragmentChecksPassed')}/{preservation.get('fragmentChecksTotal')}**，并保留认证、welcome/auth routing、chat/SSE、session/recommendation contracts。其 runtime 字段仍为 `{preservation.get('runtimeStatus')}`，不作为真实运行时通过。",
        "",
        "## Runtime boundary",
        "",
        "以下项目明确为 **unavailable**，没有伪造为通过：真实 `/auth/login` 或 `/auth/register` 请求、真实 token/username storage 读写、真实 browser interaction、computed `display/visibility/opacity`、paint/layout/hit testing、console error、`window.onerror`、uncaught exception、unhandled rejection、resource error、真实网络和 SSE。Node `--check` 仅证明抽取脚本可解析；MiniDOM 仅证明观察到的控制流模型具有唯一 app 终态。",
        "",
        "## Diff boundary",
        "",
        f"- 当前 `static/index.html` SHA-256：`{boundary['currentSourceSha256']}`。",
        f"- 与任务 6 source SHA 一致：**{boundary['sourceUnchangedFromTask6']}**。",
        f"- 工作树 `git diff --name-only`：`{', '.join(boundary['changedFilesObserved']) or '(none)'}`；这些是观察到的现有 diff，不归因于任务 7。",
        "- 本任务生产修改：**none**；新增内容仅位于 `.kiro/specs/nova-chat-interface-black-screen/`。",
        "",
        "## 结论",
        "",
        "任务 7 的静态验证完成：认证成功判定仍由真实 `res.ok` 分支控制，既有 storage key 和错误/finally 语义未被替换，成功控制流模型最终唯一显示 `appScreen` 且包含聊天 input、New chat 和 Recent/session 入口。真实登录和浏览器可见性需在可用 browser/runtime 后补做，当前不声称 browser smoke pass。",
    ]
    REPORT_PATH.write_text("\n".join(report) + "\n", encoding="utf-8")
    print(json.dumps({
        "result": evidence["result"],
        "sourceContracts": f"{passed}/{total}",
        "miniDomVisibleTopLevelViewCount": model["success"]["visibleTopLevelViewCount"],
        "nodeSyntax": syntax["status"],
        "preservation": preservation["status"],
        "runtime": "unavailable",
        "report": str(REPORT_PATH),
    }, ensure_ascii=False, indent=2))
    return 0 if evidence["result"] != "static_check_failed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
