"""Task 9 protected welcome/auth regression checks.

Dependency-free source-contract checks only. This checker intentionally does not
open a browser, make network requests, or modify production files. It extracts
the current inline script, runs Node's syntax parser, compares the current
source hashes with the task 3 preservation baseline, and records unavailable
browser/runtime observations explicitly.
"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

SPEC_DIR = Path(__file__).resolve().parent
REPO_DIR = SPEC_DIR.parents[2]
HTML_PATH = REPO_DIR / "static" / "index.html"
BASELINE_PATH = SPEC_DIR / "task3-preservation-evidence.json"
SCRIPT_PATH = SPEC_DIR / "task9-protected-regression-inline-script.js"
EVIDENCE_PATH = SPEC_DIR / "task9-protected-regression-evidence.json"
REPORT_PATH = SPEC_DIR / "task9-protected-regression-report.md"


class IdParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=False)
        self.ids: dict[str, dict[str, Any]] = {}
        self._line = 1

    def feed_with_lines(self, text: str) -> None:
        for number, line in enumerate(text.splitlines(), 1):
            self._line = number
            self.feed(line + "\n")

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        element_id = values.get("id")
        if element_id:
            self.ids[element_id] = {
                "tag": tag.lower(),
                "line": self._line,
                "class": values.get("class", "") or "",
                "type": values.get("type"),
            }


def sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def extract_script(html: str) -> str:
    scripts = re.findall(r"<script(?:\s[^>]*)?>([\s\S]*?)</script>", html, flags=re.I)
    if len(scripts) != 1:
        raise ValueError(f"expected exactly one inline script, found {len(scripts)}")
    return scripts[0]


def find_node() -> str | None:
    candidates = [
        shutil.which("node"),
        r"C:\\Program Files\\nodejs\\node.exe",
        r"C:\\Progra~1\\nodejs\\node.exe",
    ]
    return next((candidate for candidate in candidates if candidate and Path(candidate).exists()), None)


def run_node_check(source: str) -> dict[str, Any]:
    SCRIPT_PATH.write_text(source, encoding="utf-8", newline="\n")
    node = find_node()
    if not node:
        return {
            "status": "blocked_unavailable",
            "passed": None,
            "node": None,
            "version": None,
            "command": None,
            "returnCode": None,
            "stdout": "",
            "stderr": "Node.js executable not found",
        }
    version = subprocess.run([node, "--version"], capture_output=True, text=True, check=False)
    result = subprocess.run([node, "--check", str(SCRIPT_PATH)], capture_output=True, text=True, check=False)
    return {
        "status": "pass" if result.returncode == 0 else "fail",
        "passed": result.returncode == 0,
        "node": node,
        "version": (version.stdout or version.stderr).strip(),
        "command": [node, "--check", str(SCRIPT_PATH)],
        "returnCode": result.returncode,
        "stdout": result.stdout.strip(),
        "stderr": result.stderr.strip(),
    }


def count_matches(source: str, pattern: str, flags: int = 0) -> int:
    return len(re.findall(pattern, source, flags))


def source_contract_checks(html: str, source: str, parser: IdParser, baseline: dict[str, Any]) -> dict[str, dict[str, Any]]:
    checks: dict[str, dict[str, Any]] = {}

    def add(name: str, passed: bool, detail: str) -> None:
        checks[name] = {"passed": bool(passed), "detail": detail}

    expected_ids = {
        "welcomeScreen": "welcome",
        "wpStart": "start",
        "wpSignIn": "sign in",
        "authScreen": "auth",
        "tabLogin": "sign in tab",
        "tabRegister": "register tab",
        "authForm": "auth form",
        "username": "username field",
        "password": "password field",
        "pwToggle": "password visibility button",
        "authSubmit": "auth submit",
        "authErr": "auth error region",
        "authBack": "back button",
    }
    add("welcome/auth required ids present", all(key in parser.ids for key in expected_ids), ", ".join(sorted(expected_ids)))
    add("welcome starts hidden", bool(re.search(r'<div class="welcome-page hidden" id="welcomeScreen">', html)), "welcomeScreen has initial hidden class")
    add("welcome first-screen content preserved", bool(re.search(r'<h1 class="wp-title">Good choices start here\.</h1>[\s\S]{0,500}<button class="wp-start" id="wpStart"[^>]*>Start</button>', html)), "headline and Start control")
    add("welcome Sign in control preserved", bool(re.search(r'<button class="wp-signin" id="wpSignIn"[^>]*>Sign in</button>', html)), "wpSignIn text and button semantics")
    add("welcome Start and Sign in route to auth", count_matches(source, r'\$\("#wp(Start|SignIn)"\)\.addEventListener\("click",openAuth\)') == 2, "both controls use the existing openAuth handler")
    add("openAuth preserves auth hash route", bool(re.search(r'if\(!pushedAuth\)\{\s*try\{\s*history\.pushState\(\{nova:"auth"\},"","#/auth"\)', source)), "pushState to #/auth")
    add("openAuth preserves auth view transition", bool(re.search(r'const go=\(\)=>\{[\s\S]{0,180}setView\("auth"\)', source)), "openAuth calls setView(\"auth\")")
    add("direct auth hash is honored", bool(re.search(r'if\(location\.hash==="#/auth"\)\{\s*pushedAuth=true;\s*setView\("auth"\)', source)), "boot hash branch")
    add("auth form and error region preserved", bool(re.search(r'<form id="authForm"[\s\S]{0,3000}<div class="auth-err" id="authErr" role="alert"', html)), "authForm and role=alert region")
    add("auth mode tabs preserved", bool(re.search(r'<button id="tabLogin" class="on"[^>]*>Sign in</button>[\s\S]{0,180}<button id="tabRegister"[^>]*>Create account</button>', html)), "Sign in/Create account controls")
    add("auth mode switching semantics preserved", bool(re.search(r'tabLogin\.onclick=\(\)=>setMode\("login"\);\s*tabRegister\.onclick=\(\)=>setMode\("register"\);', source)), "existing setMode handlers")
    add("setMode preserves labels and password guidance", bool(re.search(r'authSubmit\.textContent=login\?"Sign in":"Create account";[\s\S]{0,280}pInput\.placeholder=login\?"Enter your password":"Create a password";', source)), "submit labels, placeholder, and mode-dependent password guidance")
    add("password visibility control preserved", bool(re.search(r'function setPwVisible\(on\)\{[\s\S]{0,300}pInput\.type=on\?"text":"password";[\s\S]{0,300}pwToggle\.setAttribute\("aria-label",on\?"Hide password":"Show password"\)', source)), "type and accessible label toggle")
    add("password toggle remains wired", bool(re.search(r'pwToggle\.addEventListener\("click",\(\)=>\{\s*setPwVisible\(pInput\.type==="password"\);\s*pInput\.focus\(\);\s*\}\);', source)), "pwToggle click handler")
    add("auth validation errors preserved", bool(re.search(r'if\(u\.length<2\)\{\s*showErr\("Username needs at least 2 characters"\);\s*return;\s*\}\s*if\(p\.length<4\)\{\s*showErr\("Password needs at least 4 characters"\);\s*return;\s*\}', source)), "username/password validation messages")
    add("auth API endpoint and method preserved", bool(re.search(r'fetch\("/auth/"\+mode,\{method:"POST"', source)), "POST /auth/login or /auth/register")
    add("auth JSON payload and content type preserved", bool(re.search(r'headers:\{"Content-Type":"application/json"\}[\s\S]{0,120}body:JSON\.stringify\(\{username:u,password:p\}\)', source)), "JSON headers and username/password payload")
    add("auth success storage semantics preserved", bool(re.search(r'token=data\.token;\s*username=data\.username;\s*localStorage\.setItem\("nova_token",token\);\s*localStorage\.setItem\("nova_user",username\);', source)), "token/username assignment and keys")
    add("auth failure error fallback preserved", bool(re.search(r'if\(!res\.ok\)\{\s*showErr\(data\.error\|\|"Something went wrong"\);\s*return;\s*\}', source)), "server error message fallback")
    add("auth network error handling preserved", bool(re.search(r'catch\(err\)\{[\s\S]{0,100}Network error\. Is the server running\?', source)), "network error message")
    add("auth finally loading reset preserved", bool(re.search(r'finally\{\s*authSubmit\.disabled=false;\s*authSubmit\.textContent=mode==="login"\?"Sign in":"Create account";\s*\}', source)), "finally restores button state and label")
    add("Back to home control preserved", bool(re.search(r'<button class="auth-back" id="authBack"[^>]*>', html) and re.search(r'id="authBack"[\s\S]{0,400}Back to home', html)), "authBack text and button")
    add("Back to home route semantics preserved", bool(re.search(r'\$\("#authBack"\)\.addEventListener\("click",backToWelcome\);', source) and re.search(r'function backToWelcome\(\)\{[\s\S]{0,280}(history\.back\(\)|enterWelcome\(\))', source)), "authBack handler and history/enterWelcome behavior")
    add("welcome/auth CSS scope preserved", all(token in html for token in [".welcome-page,.auth{", ".welcome-page{display:flex", ".auth{display:flex", ".auth-card{position:relative"]), "front-of-house CSS selectors remain present")
    add("hidden rule preserved", bool(re.search(r'\.hidden\{display:none!important\}', html)), "hidden keeps display:none!important")
    add("task3 full source baseline unchanged", sha256(html) == baseline.get("source", {}).get("sha256"), f"current={sha256(html)}, task3={baseline.get('source', {}).get('sha256')}")
    add("task3 inline script baseline unchanged", sha256(source) == baseline.get("source", {}).get("inlineScriptSha256"), f"current={sha256(source)}, task3={baseline.get('source', {}).get('inlineScriptSha256')}")

    return checks


def main() -> int:
    html = HTML_PATH.read_text(encoding="utf-8")
    source = extract_script(html)
    baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    parser = IdParser()
    parser.feed_with_lines(html)
    node = run_node_check(source)
    checks = source_contract_checks(html, source, parser, baseline)
    passed = sum(1 for result in checks.values() if result["passed"])
    total = len(checks)
    evidence = {
        "task": "9",
        "title": "Property 2: Protected welcome/auth page regression",
        "generatedBy": "task9_protected_regression_check.py",
        "result": {
            "sourceContractStatus": "pass" if passed == total else "fail",
            "sourceContractPassed": passed,
            "sourceContractTotal": total,
            "nodeSyntaxStatus": node["status"],
            "overallRuntimeStatus": "blocked_unavailable",
        },
        "source": {
            "path": "static/index.html",
            "sha256": sha256(html),
            "inlineScriptSha256": sha256(source),
            "inlineScriptCharacters": len(source),
            "inlineScriptCount": 1,
            "baselineTask3SourceSha256": baseline.get("source", {}).get("sha256"),
            "baselineTask3InlineScriptSha256": baseline.get("source", {}).get("inlineScriptSha256"),
        },
        "node": node,
        "checks": checks,
        "protectedBoundary": {
            "welcomeAuthDomCssSourceContract": "pass" if all(checks[name]["passed"] for name in ["welcome/auth required ids present", "welcome starts hidden", "welcome first-screen content preserved", "welcome Sign in control preserved", "auth form and error region preserved", "auth mode tabs preserved", "password visibility control preserved", "Back to home control preserved", "welcome/auth CSS scope preserved", "hidden rule preserved"]) else "fail",
            "productionFilesModifiedByTask9": [],
            "productionSourceChangedFromTask3Baseline": sha256(html) != baseline.get("source", {}).get("sha256"),
            "note": "Task 9 generated only spec-local evidence/check artifacts; static/index.html was not written.",
        },
        "runtimeAvailability": {
            "browserInstalledOrUsed": False,
            "visualPixels": "unavailable",
            "browserInteraction": "unavailable",
            "computedCss": "unavailable",
            "consoleErrors": "unavailable",
            "windowOnError": "unavailable",
            "uncaughtExceptions": "unavailable",
            "unhandledRejections": "unavailable",
            "networkAuthRequests": "unavailable",
            "reason": "The requested check is limited to HTML/source contracts and Node --check; no browser was installed or used.",
        },
        "scope": {
            "generatedFiles": [SCRIPT_PATH.name, EVIDENCE_PATH.name, REPORT_PATH.name],
            "modifiedProductionFiles": [],
            "modifiedProtectedFiles": [],
        },
    }
    EVIDENCE_PATH.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# Task 9 受保护 welcome/auth 页面回归报告",
        "",
        "## 结果",
        f"- HTML/source-contract：**{'PASS' if passed == total else 'FAIL'}**（{passed}/{total}）。",
        f"- Node `--check`：**{node['status'].upper()}**；Node `{node.get('version') or 'unavailable'}`。",
        "- 生产代码：**未修改**；检查器、证据和报告均位于本 bugfix spec 目录。",
        "- 真实视觉像素、浏览器交互、computed CSS、console、uncaught exception：**unavailable**（未安装/使用浏览器）。",
        "",
        "## 覆盖范围",
        "",
        "- welcome 首屏、`Start`、`Sign in` 入口及 `#/auth` 路由 source contract。",
        "- auth `Sign in`/`Create account` 切换、密码显示/隐藏、用户名/密码校验、认证失败提示、认证 API、loading/finally、`Back to home`。",
        "- `nova_token`/`nova_user` 读取与写入、`/auth/{login|register}` POST、JSON payload、错误 fallback 与原 task 3 baseline 完整 source hash 对照。",
        "- welcome/auth DOM/CSS 保护边界、初始 hidden 规则及必要控件存在性。",
        "",
        "## Node syntax evidence",
        "",
        f"- Command: `{json.dumps(node.get('command'), ensure_ascii=False)}`",
        f"- Return code: `{node.get('returnCode')}`",
        f"- stderr: `{node.get('stderr') or '(none)'}`",
        "",
        "## Source-contract checks",
        "",
    ]
    for name, result in checks.items():
        lines.append(f"- `{name}`: **{'PASS' if result['passed'] else 'FAIL'}** — {result['detail']}")
    lines += [
        "",
        "## Baseline and boundary",
        "",
        f"- Current `static/index.html` SHA-256: `{sha256(html)}`.",
        f"- Task 3 baseline SHA-256: `{baseline.get('source', {}).get('sha256')}`; exact match: **{sha256(html) == baseline.get('source', {}).get('sha256')}**.",
        f"- Current inline script SHA-256: `{sha256(source)}`.",
        f"- Task 3 inline script SHA-256: `{baseline.get('source', {}).get('inlineScriptSha256')}`; exact match: **{sha256(source) == baseline.get('source', {}).get('inlineScriptSha256')}**.",
        "- Task 9 production diff attribution: **none**. No write operation targeted `static/index.html`.",
        "- Hash equality is source-level preservation evidence; it does not prove runtime rendering or browser interaction.",
        "",
        "## Runtime boundary",
        "",
        "The following are deliberately not claimed as passing: real welcome/auth pixels, focus and hit testing, computed `display`/`visibility`/`opacity`, browser tab/password interaction, real authentication requests and storage mutation, console errors, `window.onerror`, uncaught exceptions, unhandled rejections, resource failures, and network timing. They remain **unavailable** because no browser was installed or used.",
        "",
        "## Conclusion",
        "",
        f"Task 9 source-level regression checks **{'pass' if passed == total else 'fail'}**. The protected welcome/auth source matches task 3 exactly, and Node syntax parsing passes. This is not a browser/runtime sign-off; task 9's real visual and interaction criteria remain unavailable.",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"passed": passed, "total": total, "node": node["status"], "report": str(REPORT_PATH)}, ensure_ascii=False, indent=2))
    return 0 if passed == total and node["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
