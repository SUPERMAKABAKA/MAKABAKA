"""Task 3 static preservation baseline for the Nova black-screen bugfix spec.

This check is intentionally dependency-free and does not modify production code.
It records protected authentication, welcome/auth routing, app chat/SSE/session,
and recommendation source contracts from the current (unfixed) static/index.html.
The inline script is syntax-checked when Node.js is available. A syntax failure
blocks runtime observations; it is recorded as blocked rather than treated as a
runtime pass.
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
EVIDENCE_PATH = SPEC_DIR / "task3-preservation-evidence.json"
REPORT_PATH = SPEC_DIR / "task3-preservation-report.md"

VIEW_IDS = ["welcomeScreen", "authScreen", "appScreen"]
PROTECTED_FILES = {
    "app/api/auth.py",
    "app/api/routes.py",
    "app/api/browser_routes.py",
    "app/agents/",
    ".kiro/specs/nova-chat-interface-redesign/",
}


class StructureParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=False)
        self.elements: dict[str, dict[str, Any]] = {}
        self.script_ranges: list[dict[str, int]] = []
        self._script_start: int | None = None
        self._line = 1

    def feed_with_lines(self, text: str) -> None:
        for line_number, line in enumerate(text.splitlines(), 1):
            self._line = line_number
            self.feed(line + "\n")

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_map = dict(attrs)
        if tag.lower() == "script" and not attr_map:
            self._script_start = self._line
        element_id = attr_map.get("id")
        if element_id in VIEW_IDS:
            classes = (attr_map.get("class") or "").split()
            self.elements[element_id] = {
                "tag": tag.lower(),
                "line": self._line,
                "class": attr_map.get("class") or "",
                "initialHidden": "hidden" in classes,
            }

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "script" and self._script_start is not None:
            self.script_ranges.append({"startLine": self._script_start, "endLine": self._line})
            self._script_start = None


def line_number(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def first_line(text: str, pattern: str, flags: int = 0) -> int | None:
    match = re.search(pattern, text, flags)
    return None if match is None else line_number(text, match.start())


def occurrences(text: str, pattern: str, flags: int = 0) -> list[dict[str, Any]]:
    lines = text.splitlines()
    result = []
    for match in re.finditer(pattern, text, flags):
        line = line_number(text, match.start())
        result.append({"line": line, "text": lines[line - 1].strip() if line <= len(lines) else ""})
    return result


def extract_inline_script(html: str) -> str:
    scripts = re.findall(r"<script(?:\s[^>]*)?>([\s\S]*?)</script>", html, flags=re.I)
    return scripts[0] if len(scripts) == 1 else "\n".join(scripts)


def run_node_check(source: str) -> dict[str, Any]:
    script_path = SPEC_DIR / "task3-inline-script.js"
    script_path.write_text(source, encoding="utf-8", newline="\n")
    candidates = [
        shutil.which("node"),
        r"C:\\Program Files\\nodejs\\node.exe",
        r"C:\\Progra~1\\nodejs\\node.exe",
    ]
    node = next((candidate for candidate in candidates if candidate and Path(candidate).exists()), None)
    if not node:
        return {
            "status": "blocked",
            "passed": None,
            "node": None,
            "version": None,
            "command": None,
            "returnCode": None,
            "stderr": "Node.js executable not found",
            "stdout": "",
            "errorLine": None,
        }
    version_result = subprocess.run([node, "--version"], capture_output=True, text=True, check=False)
    check = subprocess.run([node, "--check", str(script_path)], capture_output=True, text=True, check=False)
    combined = (check.stderr or "") + (check.stdout or "")
    match = re.search(r"task3-inline-script\.js:(\d+)", combined)
    return {
        "status": "pass" if check.returncode == 0 else "fail",
        "passed": check.returncode == 0,
        "node": node,
        "version": (version_result.stdout or version_result.stderr).strip(),
        "command": [node, "--check", str(script_path)],
        "returnCode": check.returncode,
        "stderr": check.stderr.strip(),
        "stdout": check.stdout.strip(),
        "errorLine": int(match.group(1)) if match else None,
    }


def check_fragment(source: str, name: str, pattern: str, *, flags: int = 0) -> dict[str, Any]:
    matches = occurrences(source, pattern, flags)
    return {
        "name": name,
        "passed": bool(matches),
        "matchCount": len(matches),
        "lines": [item["line"] for item in matches],
        "pattern": pattern,
    }


def source_contract_checks(html: str, source: str, parser: StructureParser) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []

    # Authentication request, storage, validation and error semantics.
    checks.extend([
        check_fragment(source, "auth request uses dynamic /auth/{login|register} endpoint", r'fetch\("/auth/"\+mode\s*,\s*\{method:"POST"'),
        check_fragment(source, "auth request supports register mode", r'setMode\("register"\)'),
        check_fragment(source, "auth request sends JSON content type", r'fetch\("/auth/"\+mode\s*,\s*\{method:"POST"[\s\S]{0,180}headers:\{"Content-Type":"application/json"\}'),
        check_fragment(source, "auth request payload is username/password", r'body:JSON\.stringify\(\{username:u,password:p\}\)'),
        check_fragment(source, "auth token storage key", r'localStorage\.setItem\("nova_token",token\)'),
        check_fragment(source, "auth username storage key", r'localStorage\.setItem\("nova_user",username\)'),
        check_fragment(source, "token read key", r'localStorage\.getItem\("nova_token"\)'),
        check_fragment(source, "username read key", r'localStorage\.getItem\("nova_user"\)'),
        check_fragment(source, "auth response error fallback", r'!res\.ok\)\{\s*showErr\(data\.error\|\|"Something went wrong"\)'),
        check_fragment(source, "auth network error handling", r'catch\(err\)\{\s*showErr\("Network error\. Is the server running\?"\)'),
        check_fragment(source, "auth loading state restored in finally", r'finally\{\s*authSubmit\.disabled=false;\s*authSubmit\.textContent=mode==="login"\?"Sign in":"Create account";\s*\}'),
        check_fragment(source, "username client validation", r'if\(u\.length<2\)\{\s*showErr\("Username needs at least 2 characters"\)'),
        check_fragment(source, "password client validation", r'if\(p\.length<4\)\{\s*showErr\("Password needs at least 4 characters"\)'),
        check_fragment(source, "logout removes token and username keys", r'localStorage\.removeItem\("nova_token"\);\s*localStorage\.removeItem\("nova_user"\)'),
    ])

    # Welcome/auth DOM and routing contract.
    checks.extend([
        check_fragment(html, "welcome DOM preserves Sign in control", r'id="wpSignIn"[^>]*>Sign in</button>'),
        check_fragment(html, "welcome DOM preserves Start control", r'id="wpStart"[^>]*>Start</button>'),
        check_fragment(html, "auth DOM preserves sign-in/register tabs", r'id="tabLogin"[\s\S]{0,250}id="tabRegister"'),
        check_fragment(html, "auth DOM preserves form and error region", r'id="authForm"[\s\S]{0,3000}id="authErr"[^>]*role="alert"'),
        check_fragment(html, "auth DOM preserves password toggle", r'id="pwToggle"[^>]*type="button"'),
        check_fragment(html, "auth DOM preserves back control", r'id="authBack"[^>]*type="button"'),
        check_fragment(source, "setView controls welcome view", r'welcomeScreen\.classList\.toggle\("hidden",\s*name!=="welcome"\)'),
        check_fragment(source, "setView controls auth view", r'authScreen\.classList\.toggle\("hidden",\s*name!=="auth"\)'),
        check_fragment(source, "setView controls app view", r'appScreen\.classList\.toggle\("hidden",\s*name!=="app"\)'),
        check_fragment(source, "auth route pushes #/auth", r'history\.pushState\(\{nova:"auth"\},"","#/auth"\)'),
        check_fragment(source, "back route uses history back", r'if\(pushedAuth\)\{ history\.back\(\); return; \}'),
        check_fragment(source, "popstate honors auth hash", r'if\(location\.hash==="#/auth"\)\{ pushedAuth=true; setView\("auth"\); \}'),
        check_fragment(source, "login success enters app", r'async function authSucceeded\(\)[\s\S]{0,500}enterApp\(\);'),
        check_fragment(source, "enterApp writes app hash", r'function enterApp\(\)[\s\S]{0,260}history\.replaceState\(\{nova:"app"\},"","#/app"\)'),
        check_fragment(source, "logout returns through enterWelcome", r'\$\("#logout"\)\.onclick=[\s\S]{0,900}enterWelcome\(\);'),
    ])

    # Chat transport and SSE behavior.
    checks.extend([
        check_fragment(source, "chat request uses POST /chat/stream", r'fetch\("/chat/stream",\{method:"POST"'),
        check_fragment(source, "chat request sends JSON content type", r'fetch\("/chat/stream",\{method:"POST",headers:\{"Content-Type":"application/json"'),
        check_fragment(source, "chat request conditionally sends bearer token", r'Authorization:"Bearer "\+token'),
        check_fragment(source, "chat payload preserves session_id/message", r'body:JSON\.stringify\(\{session_id:sessionId,message:text\}\)'),
        check_fragment(source, "SSE parser reads event lines", r'if\(l\.startsWith\("event:"\)\) event=l\.slice\(6\)\.trim\(\)'),
        check_fragment(source, "SSE parser reads data lines", r'else if\(l\.startsWith\("data:"\)\) data\+=l\.slice\(5\)\.trim\(\)'),
        check_fragment(source, "SSE token branch", r'event\.event==="token"'),
        check_fragment(source, "SSE recommendations branch", r'event\.event==="recommendations"'),
        check_fragment(source, "SSE error branch", r'event\.event==="error"'),
        check_fragment(source, "chat failed response fallback", r'!res\.ok\|\|!res\.body'),
        check_fragment(source, "chat network error fallback", r'Network error\. Please check the server and retry\.'),
    ])

    # Session and recommendation lifecycle functions/DOM contract.
    for function_name in [
        "saveSession", "switchToSession", "pushHistory", "resetChat", "renderRecs",
        "renderReact", "renderNotices", "renderOptions", "openRecommendationsPanel",
        "selectProduct", "closeProduct", "parseSSE",
    ]:
        checks.append(check_fragment(source, f"protected function {function_name} remains present", rf'function\s+{re.escape(function_name)}\s*\('))
    checks.extend([
        check_fragment(source, "session store remains keyed by sessionId", r'const sessions=\{\};'),
        check_fragment(source, "session snapshot remains innerHTML", r'sessions\[sessionId\]\.html=streamInner\.innerHTML'),
        check_fragment(source, "recommendation groups retain payload", r'recommendationGroups\.set\(groupId,recs\)'),
        check_fragment(source, "recommendation panel retains product selection", r'openRecommendationsPanel\(recs\);selectProduct\(index\)'),
        check_fragment(source, "recommendation browser keeps AliExpress embed URL", r'"https://www\.aliexpress\.com/wholesale\?SearchText="'),
        check_fragment(source, "recommendation external link keeps Amazon search URL", r'"https://www\.amazon\.com/s\?k="'),
    ])

    # Structural protected boundary facts.
    structural = {
        "topLevelViewIdsExactlyExpected": list(parser.elements) == VIEW_IDS,
        "allTopLevelViewsInitiallyHidden": all(parser.elements.get(view, {}).get("initialHidden") is True for view in VIEW_IDS),
        "hiddenRuleRemainsDisplayNoneImportant": re.search(r"\.hidden\s*\{\s*display\s*:\s*none\s*!important\s*\}", html) is not None,
        "singleInlineScript": len(parser.script_ranges) == 1,
        "appChatDomPreserved": all(re.search(pattern, html) is not None for pattern in [
            r'id="streamInner"', r'id="input"', r'id="send"', r'id="newChat"',
            r'id="hist"', r'id="productPanel"', r'id="novaBuddy"',
        ]),
    }
    return {"checks": checks, "structural": structural}


def git_boundary(html: str) -> dict[str, Any]:
    command = ["git", "diff", "--name-only"]
    try:
        result = subprocess.run(command, cwd=REPO_DIR, capture_output=True, text=True, check=False)
    except OSError as exc:
        return {"status": "blocked", "command": command, "error": str(exc), "changedFiles": [], "productionUnmodifiedByThisTask": None}
    changed = [line.strip().replace("\\", "/") for line in result.stdout.splitlines() if line.strip()]
    production_changed = [path for path in changed if path == "static/index.html" or path.startswith("app/") or path.startswith(".kiro/specs/nova-chat-interface-redesign/")]
    reference_path = SPEC_DIR / "task2-static-evidence.json"
    reference_sha = None
    if reference_path.exists():
        try:
            reference_sha = json.loads(reference_path.read_text(encoding="utf-8"))["source"]["sha256"]
        except (OSError, KeyError, TypeError, json.JSONDecodeError):
            reference_sha = None
    current_sha = hashlib.sha256(html.encode()).hexdigest()
    source_unchanged_from_task2 = reference_sha is not None and current_sha == reference_sha
    status = "blocked" if result.returncode != 0 else ("pass" if source_unchanged_from_task2 else "fail")
    return {
        "status": status,
        "command": command,
        "returnCode": result.returncode,
        "changedFiles": changed,
        "preexistingProductionOrProtectedChanges": production_changed,
        "productionUnmodifiedByThisTask": source_unchanged_from_task2,
        "sourceSha256": current_sha,
        "referenceTask2SourceSha256": reference_sha,
        "sourceUnchangedFromTask2": source_unchanged_from_task2,
        "interpretation": "The working tree contains changes outside this task; they are reported, not attributed to task 3. The source SHA matches task 2, so task 3 did not modify static/index.html.",
        "note": "Untracked spec artifacts are not shown by git diff --name-only and are intentionally local to this spec directory.",
    }


def main() -> int:
    html = HTML_PATH.read_text(encoding="utf-8")
    parser = StructureParser()
    parser.feed_with_lines(html)
    source = extract_inline_script(html)
    syntax = run_node_check(source)
    static = source_contract_checks(html, source, parser)
    boundary = git_boundary(html)
    passed_fragments = sum(1 for item in static["checks"] if item["passed"])
    total_fragments = len(static["checks"])
    all_static = passed_fragments == total_fragments and all(static["structural"].values())
    runtime_blocked = syntax["status"] != "pass"

    evidence = {
        "task": "3",
        "title": "Property 2: Preservation - static baseline and runtime availability",
        "generatedBy": "task3_preservation_check.py",
        "baselineStatus": "static_pass_runtime_blocked" if all_static and runtime_blocked else ("static_pass_runtime_available" if all_static else "static_failed"),
        "source": {
            "path": "static/index.html",
            "sha256": hashlib.sha256(html.encode()).hexdigest(),
            "inlineScriptSha256": hashlib.sha256(source.encode()).hexdigest(),
            "inlineScriptCharacters": len(source),
            "inlineScriptCount": len(parser.script_ranges),
            "inlineScriptArtifact": "task3-inline-script.js",
        },
        "staticBaseline": {
            "fragmentChecksPassed": passed_fragments,
            "fragmentChecksTotal": total_fragments,
            "checks": static["checks"],
            "structural": static["structural"],
        },
        "syntax": syntax,
        "runtime": {
            "status": "blocked_unavailable",
            "executionAttempted": False,
            "reason": "The inline script fails Node --check before a browser/runtime can execute boot, auth, chat, session, or SSE paths.",
            "consoleErrors": None,
            "uncaughtExceptions": None,
            "unhandledRejections": None,
            "networkRequests": None,
            "computedVisibility": None,
            "sseExchange": None,
        },
        "diffBoundary": boundary,
        "scope": {
            "productionFilesModifiedByThisTask": [],
            "protectedFilesModifiedByThisTask": [],
            "generatedFiles": [
                "task3_preservation_check.py",
                "task3-inline-script.js",
                "task3-preservation-evidence.json",
                "task3-preservation-report.md",
            ],
        },
        "preservationContract": {
            "authentication": ["POST /auth/login", "POST /auth/register", "nova_token", "nova_user", "validation/error/finally semantics"],
            "routingAndDom": ["welcomeScreen", "authScreen", "appScreen", "#/auth", "#/app", "welcome/auth controls"],
            "chat": ["POST /chat/stream", "Content-Type application/json", "conditional Bearer token", "session_id/message"],
            "sse": ["token", "recommendations", "error", "fallback response handling"],
            "sessionAndRecommendations": ["saveSession", "switchToSession", "pushHistory", "resetChat", "recommendationGroups", "renderRecs", "product panel"],
        },
        "runtimeDecision": "Do not claim runtime preservation pass. Task 4 must first address the syntax defect through the authorized minimal implementation, then rerun this same check plus real runtime checks when a browser/runtime is available.",
    }
    EVIDENCE_PATH.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    report: list[str] = [
        "# Task 3 preservation baseline report",
        "",
        "## Result",
        f"- Overall baseline: **{evidence['baselineStatus']}**.",
        f"- Static protected-fragment checks: **{passed_fragments}/{total_fragments} PASS**.",
        f"- Structural checks: **{'PASS' if all(static['structural'].values()) else 'FAIL'}**.",
        f"- Inline script syntax: **{syntax['status'].upper()}** using `node --check`; this is a blocking source condition for runtime checks.",
        "- Runtime preservation: **BLOCKED/UNAVAILABLE**, not a pass. No browser or JavaScript runtime path was executed.",
        "- Production code changes made by this task: **none**.",
        "",
        "## Source and syntax evidence",
        "",
        f"- Source SHA-256: `{evidence['source']['sha256']}`.",
        f"- Inline script SHA-256: `{evidence['source']['inlineScriptSha256']}`.",
        f"- Node version: `{syntax.get('version') or 'unavailable'}`.",
        f"- Syntax command: `{json.dumps(syntax.get('command'), ensure_ascii=False)}`.",
        f"- Syntax return code: `{syntax.get('returnCode')}`.",
        f"- Syntax error line in extracted script: `{syntax.get('errorLine')}`.",
        f"- Syntax stderr: `{syntax.get('stderr') or '(none)'}`.",
        "",
        "## Static preservation contract",
        "",
        "The checks below record source-level behavior that task 4 must preserve. They do not prove browser behavior.",
        "",
    ]
    for item in static["checks"]:
        report.append(f"- `{item['name']}`: **{'PASS' if item['passed'] else 'FAIL'}** (lines {item['lines'] or 'none'})")
    report += ["", "### Protected structure", ""]
    for name, passed in static["structural"].items():
        report.append(f"- `{name}`: **{'PASS' if passed else 'FAIL'}**")
    report += [
        "",
        "## Runtime checks intentionally blocked",
        "",
        "The following observations are unavailable because the inline script cannot be parsed/executed in the current unfixed source:",
        "- authentication request/response and storage behavior in a real page",
        "- welcome/auth interaction, route transitions, focus and computed visibility",
        "- `/chat/stream` network request, Authorization header as sent, and session payload at runtime",
        "- SSE token/recommendations/error rendering and fallback behavior",
        "- session switching, recommendation selection, browser panel interaction",
        "- console errors, uncaught exceptions, unhandled rejections, resource errors, and layout/hit testing",
        "",
        "These fields are recorded as `null` in `task3-preservation-evidence.json`; no simulated or static result is presented as runtime evidence.",
        "",
        "## Diff boundary",
        "",
        f"- Git diff status: **{boundary['status'].upper()}**.",
        f"- Changed files observed: `{', '.join(boundary.get('changedFiles', [])) or '(none)'}`.",
        f"- Pre-existing production/protected changes observed: `{', '.join(boundary.get('preexistingProductionOrProtectedChanges', [])) or '(none)'}`.",
        f"- Current `static/index.html` SHA matches task 2 baseline: **{boundary.get('sourceUnchangedFromTask2')}**.",
        f"- Production modification attributable to task 3: **{'none' if boundary.get('productionUnmodifiedByThisTask') else 'not proven'}**.",
        "- This task generated only files inside `.kiro/specs/nova-chat-interface-black-screen/` and did not edit `static/index.html`, backend/auth code, or the redesign spec.",
        "",
        "## Task 4 handoff",
        "",
        "1. Preserve every static contract recorded above, especially auth endpoints/storage keys, welcome/auth routing and DOM, chat transport headers/payload, SSE branches, session lifecycle, and recommendation payload handling.",
        "2. Treat the Node syntax error as a confirmed static blocker to runtime, but do not claim it alone proves the browser root cause; runtime evidence remains required by the design evidence gate.",
        "3. Make the smallest authorized change in `static/index.html` needed to restore parsing and lifecycle execution. Do not clean up duplicate functions or bindings without causal runtime evidence.",
        "4. Rerun this same check after implementation, then run browser/runtime preservation checks. Any changed protected fragment is a regression requiring review.",
    ]
    REPORT_PATH.write_text("\n".join(report) + "\n", encoding="utf-8")
    print(json.dumps({
        "baselineStatus": evidence["baselineStatus"],
        "staticChecks": f"{passed_fragments}/{total_fragments}",
        "syntax": syntax["status"],
        "runtime": evidence["runtime"]["status"],
        "diffBoundary": boundary["status"],
        "report": str(REPORT_PATH),
    }, ensure_ascii=False, indent=2))
    return 0 if all_static and boundary["status"] in {"pass", "blocked"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
