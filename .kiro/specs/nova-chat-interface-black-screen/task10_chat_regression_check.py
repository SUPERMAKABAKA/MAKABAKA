"""Task 10 source-contract/model regression check for app chat and protected payloads.

This check reuses task 3's preservation evidence and adds focused, dependency-free
source/model assertions for chat transport, SSE, session lifecycle, and recommendation
rendering. It intentionally does not open a browser, make network requests, or write
production files. Runtime fields are recorded as unavailable rather than inferred.
"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

SPEC_DIR = Path(__file__).resolve().parent
REPO_DIR = SPEC_DIR.parents[2]
HTML_PATH = REPO_DIR / "static" / "index.html"
BASELINE_PATH = SPEC_DIR / "task3-preservation-evidence.json"
SCRIPT_PATH = SPEC_DIR / "task10-chat-regression-inline-script.js"
EVIDENCE_PATH = SPEC_DIR / "task10-chat-regression-evidence.json"
REPORT_PATH = SPEC_DIR / "task10-chat-regression-report.md"


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


def check(source: str, pattern: str, *, flags: int = 0) -> dict[str, Any]:
    matches = list(re.finditer(pattern, source, flags))
    return {"passed": bool(matches), "matchCount": len(matches), "pattern": pattern}


def model_checks(source: str) -> dict[str, dict[str, Any]]:
    checks: dict[str, dict[str, Any]] = {}

    def add(name: str, pattern: str, flags: int = 0) -> None:
        checks[name] = check(source, pattern, flags=flags)

    # Chat request contract and lifecycle fallbacks.
    add("chat endpoint is POST /chat/stream", r'fetch\("/chat/stream",\{method:"POST"')
    add("chat request declares JSON content type", r'fetch\("/chat/stream",\{method:"POST",headers:\{"Content-Type":"application/json"')
    add("chat request conditionally sends bearer token", r'\(token\?\{Authorization:"Bearer "\+token\}:\{\}\)')
    add("chat request sends session_id and message", r'body:JSON\.stringify\(\{session_id:sessionId,message:text\}\)')
    add("non-ok or missing body uses request fallback", r'if\(!res\.ok\|\|!res\.body\)')
    add("request fallback preserves failure copy", r'Sorry, the request failed\. Please try again\.')
    add("network catch preserves network fallback", r'Network error\. Please check the server and retry\.')
    add("send lifecycle resets busy and send state", r'finally\{busy=false;syncSendState\(\);input\.focus\(\);scrollDown\(\);saveSession\(\);\}')

    # SSE framing, JSON fallback, and event-specific behavior.
    add("SSE parser reads event lines", r'if\(l\.startsWith\("event:"\)\) event=l\.slice\(6\)\.trim\(\)')
    add("SSE parser reads data lines", r'else if\(l\.startsWith\("data:"\)\) data\+=l\.slice\(5\)\.trim\(\)')
    add("SSE parser JSON-decodes data", r'try\{ return \{event,data:JSON\.parse\(data\|\|"\{\}"\)\}; \}catch\{ return \{event,data:\{\}\}; \}')
    add("SSE token event appends token text", r'event\.event==="token"\)appendToken\(body,event\.data\.text\|\|"",caret\)')
    add("SSE recommendations event retains response data", r'event\.event==="recommendations"\)responseData=event\.data')
    add("SSE error event appends error text", r'event\.event==="error"\)appendToken\(body,event\.data\.error\|\|"Request failed",caret\)')
    add("SSE stream is split on blank event frames", r'while\(\(divider=buffer\.indexOf\("\\n\\n"\)\)>=0\)')

    # Session store and lifecycle model.
    add("session store is keyed by sessionId", r'const sessions=\{\};')
    add("saveSession stores stream innerHTML", r'function saveSession\(\)\{ if\(sessions\[sessionId\]\) sessions\[sessionId\]\.html=streamInner\.innerHTML; \}')
    add("pushHistory creates session snapshot", r'function pushHistory\(text\)\{[\s\S]{0,500}sessions\[sessionId\]=\{title,html:streamInner\.innerHTML\}', re.S)
    add("switchToSession restores session snapshot", r'function switchToSession\(id\)\{[\s\S]{0,500}sessionId=id; streamInner\.innerHTML=sessions\[id\]\.html;', re.S)
    add("resetChat creates new session and restores welcome", r'function resetChat\(\)\{[\s\S]{0,650}sessionId=newId\(\); streamInner\.innerHTML=""; streamInner\.appendChild\(welcome\);', re.S)
    add("history click switches selected session", r'histEl\.addEventListener\("click",event=>\{const item=event\.target\.closest\("\.hist-item"\);if\(item\)switchToSession\(item\.dataset\.session\);\}')
    add("send creates history entry for a new session", r'if\(!sessions\[sessionId\]\)pushHistory\(text\)')

    # Recommendation payload, ranking/content rendering, and product selection.
    add("recommendation payload is retained by group", r'recommendationGroups\.set\(groupId,recs\)')
    add("recommendation title and product fallback render", r'rec\.title\|\|rec\.product_id\|\|"Product"')
    add("recommendation reason is escaped and rendered", r'class="rec-reason">\'\+esc\(rec\.reason\|\|""\)')
    add("recommendation positives and negatives are bounded", r'positives\|\|\[\]\)\.slice\(0,3\),neg=\(rec\.summary&&rec\.summary\.negatives\|\|\[\]\)\.slice\(0,3\)')
    add("recommendation rank is derived from display index", r'String\(index\+1\)\.padStart\(2,"0"\)')
    add("insufficient recommendation status keeps notice", r'if\(status==="insufficient"\)renderNotices\(container,\["Few items matched\. Showing all available results\."\]\)')
    add("recommendation click resolves payload and index", r'const recs=recommendationGroups\.get\(card\.dataset\.recGroup\);const index=Number\(card\.dataset\.recIndex\);')
    add("recommendation click opens panel and selects product", r'openRecommendationsPanel\(recs\);selectProduct\(index\)')
    add("product panel maps recommendation titles and queries", r'brProducts=\(recs\|\|\[\]\)\.map\(r=>\(\{title:r\.title\|\|r\.product_id\|\|"Product",q:r\.title\|\|r\.product_id\|\|"product"\}\)\)')
    add("AliExpress embed URL is preserved", r'return "https://www\.aliexpress\.com/wholesale\?SearchText="\+encodeURIComponent\(q\)')
    add("Amazon external search URL is preserved", r'return "https://www\.amazon\.com/s\?k="\+encodeURIComponent\(q\)')
    add("selectProduct sets iframe and external link", r'frame\.src=url; \$\("#ppWebwrap"\)\.classList\.add\("live"\);[\s\S]{0,240}\$\("#ppExt"\)\.href=extShopUrl\(product\.q\)', re.S)
    add("closeProduct clears panel and iframe", r'function closeProduct\(\{restoreFocus=true\}=\{\}\)\{[\s\S]{0,500}frame\.src="about:blank";', re.S)

    return checks


def git_diff_names() -> list[str]:
    result = subprocess.run(["git", "diff", "--name-only"], cwd=REPO_DIR, capture_output=True, text=True, check=False)
    return [line.strip().replace("\\", "/") for line in result.stdout.splitlines() if line.strip()]


def main() -> int:
    html = HTML_PATH.read_text(encoding="utf-8")
    source = extract_script(html)
    baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    task3_static = baseline.get("staticBaseline", {})
    task3_checks_passed = task3_static.get("fragmentChecksPassed")
    task3_checks_total = task3_static.get("fragmentChecksTotal")
    task3_structural = task3_static.get("structural", {})
    task3_structure_passed = sum(1 for value in task3_structural.values() if value is True)
    task3_structure_total = len(task3_structural)
    task3_syntax = baseline.get("syntax", {})

    checks = model_checks(source)
    model_passed = sum(1 for result in checks.values() if result["passed"])
    model_total = len(checks)
    node = run_node_check(source)
    current_source_sha = sha256(html)
    current_script_sha = sha256(source)
    baseline_source_sha = baseline.get("source", {}).get("sha256")
    baseline_script_sha = baseline.get("source", {}).get("inlineScriptSha256")
    diff_names = git_diff_names()

    evidence = {
        "task": "10",
        "title": "Property 2: app chat/session/SSE and protected payload regression",
        "generatedBy": "task10_chat_regression_check.py",
        "reusedChecks": {
            "task3Evidence": "task3-preservation-evidence.json",
            "task3StaticSourceContracts": {
                "passed": task3_checks_passed,
                "total": task3_checks_total,
                "status": "pass" if task3_checks_passed == task3_checks_total else "fail",
            },
            "task3ProtectedStructure": {
                "passed": task3_structure_passed,
                "total": task3_structure_total,
                "status": "pass" if task3_structure_passed == task3_structure_total else "fail",
                "checks": task3_structural,
            },
            "task3NodeSyntax": {
                "status": task3_syntax.get("status"),
                "passed": task3_syntax.get("passed"),
                "node": task3_syntax.get("node"),
                "version": task3_syntax.get("version"),
            },
        },
        "modelChecks": {
            "passed": model_passed,
            "total": model_total,
            "status": "pass" if model_passed == model_total else "fail",
            "checks": checks,
        },
        "node": node,
        "source": {
            "path": "static/index.html",
            "sha256": current_source_sha,
            "inlineScriptSha256": current_script_sha,
            "inlineScriptCharacters": len(source),
            "inlineScriptCount": 1,
            "task3BaselineSha256": baseline_source_sha,
            "task3BaselineInlineScriptSha256": baseline_script_sha,
            "sourceMatchesTask3Baseline": current_source_sha == baseline_source_sha,
            "inlineScriptMatchesTask3Baseline": current_script_sha == baseline_script_sha,
        },
        "runtimeAvailability": {
            "status": "blocked_unavailable",
            "browserInstalledOrUsed": False,
            "chatRequest": "unavailable",
            "sseExchange": "unavailable",
            "sessionUi": "unavailable",
            "recommendationUi": "unavailable",
            "networkRequests": "unavailable",
            "consoleErrors": "unavailable",
            "uncaughtExceptions": "unavailable",
            "unhandledRejections": "unavailable",
            "reason": "No browser was installed or used; this task records source/model evidence only and does not claim runtime behavior.",
        },
        "diffBoundary": {
            "productionFilesModifiedByTask10": [],
            "specLocalFilesGeneratedByTask10": [
                SCRIPT_PATH.name,
                EVIDENCE_PATH.name,
                REPORT_PATH.name,
            ],
            "observedGitDiffNames": diff_names,
            "productionSourceChangedFromTask3Baseline": current_source_sha != baseline_source_sha,
            "note": "The checker writes only files under this bugfix spec directory; static/index.html is read-only input.",
        },
        "overall": {
            "status": "pass" if (
                task3_checks_passed == task3_checks_total
                and task3_structure_passed == task3_structure_total
                and task3_syntax.get("status") == "pass"
                and model_passed == model_total
                and node["status"] == "pass"
                and current_source_sha == baseline_source_sha
                and current_script_sha == baseline_script_sha
            ) else "fail",
            "runtime": "unavailable",
        },
    }
    EVIDENCE_PATH.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    overall_pass = evidence["overall"]["status"] == "pass"
    lines = [
        "# Task 10 app chat/session/SSE 与受保护 payload 回归报告",
        "",
        "## 结果",
        f"- 总体 source/model regression：**{'PASS' if overall_pass else 'FAIL'}**。",
        f"- 复用 task 3 preservation source contracts：**{task3_checks_passed}/{task3_checks_total} PASS**。",
        f"- 复用 task 3 protected structure：**{task3_structure_passed}/{task3_structure_total} PASS**。",
        f"- Node `--check`：**{node['status'].upper()}**（{node.get('version') or 'unavailable'}）。",
        f"- task 10 focused chat/session/SSE/payload model checks：**{model_passed}/{model_total} PASS**。",
        "- 生产代码：**未修改**；本检查器只生成 bugfix spec 目录内的证据文件。",
        "- 真实 chat request、SSE exchange、session UI、recommendation UI、network、console：**unavailable**；未伪造 runtime pass。",
        "",
        "## 覆盖的 source/model contracts",
        "",
        "### Chat transport and fallback",
        "- `POST /chat/stream`。",
        "- `Content-Type: application/json`、条件式 `Authorization: Bearer <token>`。",
        "- `session_id`/`message` JSON payload。",
        "- non-OK/missing body fallback、network catch fallback，以及 finally 中的 busy/send/session 保存生命周期。",
        "",
        "### SSE",
        "- `event:`/`data:` 行解析、空行分帧、JSON decode fallback。",
        "- `token`、`recommendations`、`error` 三类事件分支及其渲染/数据保留行为。",
        "",
        "### Session lifecycle",
        "- `sessions` keyed by `sessionId`、`saveSession` innerHTML snapshot。",
        "- `pushHistory` 创建会话、`switchToSession` 恢复会话、`resetChat` 新建会话并恢复 welcome。",
        "- history click switching 与新 session 的 history entry。",
        "",
        "### Recommendation payload and product selection",
        "- recommendation group payload preservation、title/product fallback、reason、positives/negatives、rank formatting、insufficient notice。",
        "- delegated card selection、`openRecommendationsPanel`、`selectProduct`、`closeProduct`。",
        "- AliExpress iframe URL 与 Amazon external search URL。",
        "",
        "## Focused model checks",
        "",
    ]
    for name, result in checks.items():
        lines.append(f"- `{name}`: **{'PASS' if result['passed'] else 'FAIL'}**")
    lines += [
        "",
        "## Reused task 3 evidence",
        "",
        f"- Task 3 evidence file: `{BASELINE_PATH.name}`。",
        f"- Task 3 static contracts: **{task3_checks_passed}/{task3_checks_total}**。",
        f"- Task 3 protected structure: **{task3_structure_passed}/{task3_structure_total}**。",
        f"- Task 3 recorded Node syntax: **{task3_syntax.get('status', 'unknown').upper()}**。",
        "- Task 3 runtime status is not treated as a pass; browser/runtime remains unavailable for this task.",
        "",
        "## Source and boundary evidence",
        "",
        f"- Current `static/index.html` SHA-256: `{current_source_sha}`。",
        f"- Task 3 baseline SHA-256: `{baseline_source_sha}`；exact match: **{current_source_sha == baseline_source_sha}**。",
        f"- Current inline script SHA-256: `{current_script_sha}`。",
        f"- Task 3 inline script SHA-256: `{baseline_script_sha}`；exact match: **{current_script_sha == baseline_script_sha}**。",
        f"- Observed `git diff --name-only`: `{', '.join(diff_names) or '(none)'}`。",
        "- Task 10 wrote no production file and made no request to modify `static/index.html`。",
        "",
        "## Runtime boundary",
        "",
        "以下项目明确为 **unavailable**，不能由本 source/model check 推断为通过：真实 `/chat/stream` request/header/payload、SSE token/recommendations/error exchange、session 新建/切换/reset UI、推荐 card 点击与 product panel、network timing、console error、uncaught exception、unhandled rejection、computed visibility 和 browser hit testing。",
        "",
        "## Conclusion",
        "",
        f"Task 10 的静态/模型检查{'通过' if overall_pass else '未通过'}；该结论不等同于浏览器 runtime sign-off。",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({
        "overall": evidence["overall"]["status"],
        "task3Static": f"{task3_checks_passed}/{task3_checks_total}",
        "task3Structure": f"{task3_structure_passed}/{task3_structure_total}",
        "modelChecks": f"{model_passed}/{model_total}",
        "node": node["status"],
        "runtime": evidence["runtimeAvailability"]["status"],
        "report": str(REPORT_PATH),
    }, ensure_ascii=False, indent=2))
    return 0 if overall_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
