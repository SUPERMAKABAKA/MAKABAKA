"""Task 2 static checks for the Nova black-screen bugfix spec.

This is dependency-free and intentionally does not open a browser or modify
production code. It extracts the single inline script to a spec-local artifact,
then invokes the installed Node.js parser with `node --check`. All diagnostics
and generated artifacts remain in this spec directory.
"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import sys
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

SPEC_DIR = Path(__file__).resolve().parent
REPO_DIR = SPEC_DIR.parents[2]
HTML_PATH = REPO_DIR / "static" / "index.html"
SCRIPT_PATH = SPEC_DIR / "task2-inline-script.js"
EVIDENCE_PATH = SPEC_DIR / "task2-static-evidence.json"
REPORT_PATH = SPEC_DIR / "task2-static-report.md"

VIEW_IDS = ["welcomeScreen", "authScreen", "appScreen"]
VIEW_NAMES = {"welcome": "welcomeScreen", "auth": "authScreen", "app": "appScreen"}


class StructureParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=False)
        self.elements: dict[str, dict[str, Any]] = {}
        self.inline_scripts: list[dict[str, int]] = []
        self._script_start: int | None = None
        self._line = 1

    def feed_with_lines(self, text: str) -> None:
        lines = text.splitlines()
        for line_number, line in enumerate(lines, 1):
            self._line = line_number
            self.feed(line + "\n")

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_map = dict(attrs)
        if tag.lower() == "script" and not attr_map:
            self._script_start = self._line
        if attr_map.get("id") in VIEW_IDS:
            self.elements[attr_map["id"]] = {
                "tag": tag.lower(),
                "line": self._line,
                "class": attr_map.get("class", "") or "",
                "initialHidden": "hidden" in (attr_map.get("class", "") or "").split(),
            }

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "script" and self._script_start is not None:
            self.inline_scripts.append({"startLine": self._script_start, "endLine": self._line})
            self._script_start = None


def line_number(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def source_line(source: str, needle: str, start: int = 0) -> int | None:
    match = re.search(re.escape(needle), source[start:])
    return None if match is None else line_number(source, start + match.start())


def html_line(html: str, needle: str) -> int | None:
    return source_line(html, needle)


def find_function_bodies(source: str) -> dict[str, list[dict[str, Any]]]:
    """Find named function ranges using brace matching that skips JS strings/comments."""
    result: dict[str, list[dict[str, Any]]] = {}
    pattern = re.compile(r"\bfunction\s+([A-Za-z_$][\w$]*)\s*\(")
    for match in pattern.finditer(source):
        name = match.group(1)
        brace = source.find("{", match.end())
        if brace < 0:
            continue
        depth = 0
        state = "code"
        quote = ""
        escaped = False
        i = brace
        end = None
        while i < len(source):
            ch = source[i]
            nx = source[i + 1] if i + 1 < len(source) else ""
            if state == "line":
                if ch == "\n": state = "code"
            elif state == "block":
                if ch == "*" and nx == "/": state = "code"; i += 1
            elif state in {"string", "template"}:
                if escaped: escaped = False
                elif ch == "\\": escaped = True
                elif ch == quote: state = "code"
            else:
                if ch == "/" and nx == "/": state = "line"; i += 1
                elif ch == "/" and nx == "*": state = "block"; i += 1
                elif ch in "'\"`": state = "template" if ch == "`" else "string"; quote = ch
                elif ch == "{": depth += 1
                elif ch == "}":
                    depth -= 1
                    if depth == 0:
                        end = i
                        break
            i += 1
        if end is not None:
            result.setdefault(name, []).append({
                "startLine": line_number(source, match.start()),
                "endLine": line_number(source, end),
                "start": match.start(),
                "end": end,
                "body": source[brace + 1:end],
            })
    return result


def occurrences(source: str, pattern: str) -> list[dict[str, Any]]:
    return [{"line": line_number(source, m.start()), "text": source.splitlines()[line_number(source, m.start()) - 1].strip()}
            for m in re.finditer(pattern, source)]


def duplicate_function_risks(source: str, functions: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    return [{"name": name, "lines": [item["startLine"] for item in defs], "classification": "unconfirmed-risk"}
            for name, defs in functions.items() if len(defs) > 1]


def event_binding_risks(source: str) -> list[dict[str, Any]]:
    patterns = {
        "input.addEventListener": r"\binput\.addEventListener\s*\(",
        "sendBtn.addEventListener": r"\bsendBtn\.addEventListener\s*\(",
        "streamInner.addEventListener": r"\bstreamInner\.addEventListener\s*\(",
        "histEl.addEventListener": r"\bhistEl\.addEventListener\s*\(",
        "#newChat.onclick": r"\$\(\"#newChat\"\)\.onclick\s*=",
        "#sideToggle.onclick": r"\$\(\"#sideToggle\"\)\.onclick\s*=",
        "#ppClose.onclick": r"\$\(\"#ppClose\"\)\.onclick\s*=",
        "#nbNewChat.onclick": r"\$\(\"#nbNewChat\"\)\.onclick\s*=",
        "#novaBuddy.onclick": r"\$\(\"#novaBuddy\"\)\.onclick\s*=",
    }
    risks = []
    for target, pattern in patterns.items():
        found = occurrences(source, pattern)
        if len(found) > 1:
            risks.append({"target": target, "count": len(found), "occurrences": found, "classification": "unconfirmed-risk"})
    return risks


def run_node_check(source: str) -> dict[str, Any]:
    SCRIPT_PATH.write_text(source, encoding="utf-8", newline="\n")
    candidates = [
        shutil.which("node"),
        r"C:\\Program Files\\nodejs\\node.exe",
        r"C:\\Progra~1\\nodejs\\node.exe",
    ]
    node = next((item for item in candidates if item and Path(item).exists()), None)
    if not node:
        return {"status": "blocked", "passed": None, "node": None, "version": None,
                "command": None, "stderr": "Node.js executable not found", "errorLine": None}
    version_result = subprocess.run([node, "--version"], capture_output=True, text=True, check=False)
    check = subprocess.run([node, "--check", str(SCRIPT_PATH)], capture_output=True, text=True, check=False)
    error_line = None
    combined = (check.stderr or "") + (check.stdout or "")
    match = re.search(r"(?:task2-inline-script\.js|<anonymous>):(\d+)", combined)
    if match:
        error_line = int(match.group(1))
    return {
        "status": "pass" if check.returncode == 0 else "fail",
        "passed": check.returncode == 0,
        "node": node,
        "version": (version_result.stdout or version_result.stderr).strip(),
        "command": [node, "--check", str(SCRIPT_PATH)],
        "returnCode": check.returncode,
        "stderr": check.stderr.strip(),
        "stdout": check.stdout.strip(),
        "errorLine": error_line,
    }


def lifecycle_checks(html: str, source: str, parser: StructureParser, functions: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    set_view = functions.get("setView", [{}])[0]
    enter_app = functions.get("enterApp", [{}])[0]
    enter_welcome = functions.get("enterWelcome", [{}])[0]
    set_body = set_view.get("body", "")
    checks = {
        "topLevelViewIdsExactlyExpected": list(parser.elements) == VIEW_IDS,
        "allTopLevelViewsInitiallyHidden": all(parser.elements.get(v, {}).get("initialHidden") is True for v in VIEW_IDS),
        "hiddenCssUsesImportantDisplayNone": re.search(r"\.hidden\s*\{\s*display\s*:\s*none\s*!important\s*\}", html) is not None,
        "setViewTogglesHiddenForEachView": all(re.search(rf"{v}\.classList\.toggle\(\s*['\"]hidden['\"]\s*,\s*name\s*!==\s*['\"]{name}['\"]", set_body) for name, v in VIEW_NAMES.items()),
        "setViewSetsFrontForNonApp": re.search(r"body\.classList\.toggle\(\s*['\"]front['\"]\s*,\s*name\s*!==\s*['\"]app['\"]", set_body) is not None,
        "enterAppCallsSetViewApp": re.search(r"setView\(\s*['\"]app['\"]\s*\)", enter_app.get("body", "")) is not None,
        "enterWelcomeCallsSetViewWelcome": re.search(r"setView\(\s*['\"]welcome['\"]\s*\)", enter_welcome.get("body", "")) is not None,
        "bootHasAuthenticatedBranch": re.search(r"if\s*\(\s*token\s*&&\s*username\s*\)\s*\{\s*enterApp\(\s*\)", source) is not None,
        "bootHonorsAuthHash": re.search(r"location\.hash\s*===\s*['\"]#/auth['\"]", source) is not None,
        "logoutClearsTokenAndUser": all(re.search(rf"localStorage\.removeItem\(\s*['\"]nova_{key}['\"]\s*\)", source) for key in ("token", "user")),
        "logoutCallsEnterWelcome": re.search(r"\$\(\s*['\"]#logout['\"]\s*\)\.onclick\s*=.*?enterWelcome\(\s*\)", source, re.S) is not None,
    }
    visibility = {
        "setViewMapping": {name: view for name, view in VIEW_NAMES.items()},
        "allViewsMutuallyExcludedByForcedHidden": checks["setViewTogglesHiddenForEachView"],
        "initialVisibleViewCount": 0,
        "expectedTerminalVisibleViewCountAfterSetView": 1 if checks["setViewTogglesHiddenForEachView"] else None,
    }
    line_facts = {
        "viewElementLines": {v: parser.elements.get(v, {}).get("line") for v in VIEW_IDS},
        "hiddenCssLine": html_line(html, ".hidden{display:none!important}"),
        "setViewLine": set_view.get("startLine"),
        "enterAppLine": enter_app.get("startLine"),
        "enterWelcomeLine": enter_welcome.get("startLine"),
        "authenticatedBootLine": source_line(source, "if(token&&username){ enterApp(); }") or source_line(source, "if(token&&username)"),
        "logoutHandlerLine": source_line(source, '$("#logout").onclick='),
    }
    return {"checks": checks, "visibility": visibility, "lineFacts": line_facts}


def main() -> int:
    html = HTML_PATH.read_text(encoding="utf-8")
    parser = StructureParser()
    parser.feed_with_lines(html)
    script_matches = re.findall(r"<script(?:\s[^>]*)?>([\s\S]*?)</script>", html, flags=re.I)
    source = script_matches[0] if len(script_matches) == 1 else "\n".join(script_matches)
    functions = find_function_bodies(source)
    node_check = run_node_check(source)
    if node_check.get("errorLine") and parser.inline_scripts:
        # The extracted script starts on the line after the opening <script> tag.
        node_check["htmlErrorLine"] = parser.inline_scripts[0]["startLine"] + node_check["errorLine"]
        source_lines = source.splitlines()
        node_check["errorSourceLine"] = source_lines[node_check["errorLine"] - 1] if node_check["errorLine"] <= len(source_lines) else None
    else:
        node_check["htmlErrorLine"] = None
        node_check["errorSourceLine"] = None
    static = lifecycle_checks(html, source, parser, functions)
    evidence = {
        "task": "2",
        "title": "Property 1: Bug Condition - static startup/HTML/JS/visibility checks",
        "generatedBy": "task2_static_check.py",
        "source": {
            "path": "static/index.html",
            "sha256": hashlib.sha256(html.encode()).hexdigest(),
            "inlineScriptCount": len(script_matches),
            "inlineScriptSha256": hashlib.sha256(source.encode()).hexdigest(),
            "inlineScriptCharacters": len(source),
            "inlineScriptArtifact": SCRIPT_PATH.name,
        },
        "node": node_check,
        "htmlStructure": {
            "topLevelViews": parser.elements,
            "inlineScriptTags": parser.inline_scripts,
            "parseMethod": "Python stdlib HTMLParser plus explicit source assertions",
        },
        "lifecycle": static,
        "risks": {
            "duplicateFunctionDefinitions": duplicate_function_risks(source, functions),
            "duplicateEventBindingPatterns": event_binding_risks(source),
            "classification": "unconfirmed-risk-only; no causal root-cause claim",
        },
        "rootCauseAssessment": {
            "staticSyntaxDefect": node_check["status"] == "fail",
            "staticRootCauseConfirmed": False,
            "staticRootCauseCandidate": node_check["status"] == "fail" and static["checks"]["allTopLevelViewsInitiallyHidden"],
            "associatedStaticRisk": bool(node_check["status"] == "fail" or event_binding_risks(source)),
            "causalRuntimeConfirmation": False,
            "reason": "The parser failure would prevent boot/setView code from executing while all three top-level views start hidden, so it is a strong static black-screen candidate. Browser/runtime causality remains unconfirmed because no browser was used.",
        },
        "scope": {
            "browserInstalledOrUsed": False,
            "productionFilesModified": [],
            "protectedFilesModified": [],
            "generatedFiles": [SCRIPT_PATH.name, EVIDENCE_PATH.name, REPORT_PATH.name],
        },
        "nextStep": "allow_preservation_and_implementation_only_if_node_syntax_passes_and_task_1_runtime_evidence_has_met_the_design evidence gate",
    }
    EVIDENCE_PATH.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    checks = static["checks"]
    report = [
        "# Task 2 static startup/HTML/JS/visibility report",
        "",
        "## Result",
        f"- JavaScript syntax: **{node_check['status'].upper()}** using `node --check`.",
        f"- Node.js: `{node_check.get('version') or 'unavailable'}`; executable: `{node_check.get('node') or 'none'}`.",
        f"- Inline script extraction: **{'PASS' if len(script_matches) == 1 else 'FAIL'}** ({len(script_matches)} inline script block(s)); artifact: `{SCRIPT_PATH.name}`.",
        "- Browser: not installed or used, as requested.",
        "- Production changes: none; all generated artifacts are in this spec directory.",
        "",
        "## Syntax evidence",
        "",
        f"- Command: `{json.dumps(node_check.get('command'), ensure_ascii=False)}`",
        f"- Return code: `{node_check.get('returnCode', 'blocked')}`",
        f"- Error line in extracted script: `{node_check.get('errorLine')}`; corresponding HTML line: `{node_check.get('htmlErrorLine')}`",
        f"- Exact source line: `{node_check.get('errorSourceLine') or '(none)'}`",
        f"- Exact stderr: `{node_check.get('stderr') or '(none)'}`",
        "",
        "## HTML and lifecycle facts",
        "",
    ]
    for key, value in checks.items():
        report.append(f"- `{key}`: **{'PASS' if value else 'FAIL'}**")
    report += [
        "",
        "### Precise source lines",
        "",
    ]
    for key, value in static["lineFacts"].items():
        report.append(f"- `{key}`: `{value}`")
    report += [
        "",
        "### Visibility mutual exclusion",
        "",
        f"- Initial top-level visible count before lifecycle code: `{static['visibility']['initialVisibleViewCount']}` because all three source nodes start with `hidden`.",
        f"- `setView()` forced-hidden mapping covers all three views: **{static['visibility']['allViewsMutuallyExcludedByForcedHidden']}**.",
        f"- Expected modeled terminal count after a valid `setView(name)`: `{static['visibility']['expectedTerminalVisibleViewCountAfterSetView']}`. This is a static invariant, not browser computed-style evidence.",
        "",
        "## Duplicate definitions and event-binding risk inventory",
        "",
        "These findings are **unconfirmed risks only**. They are not treated as a black-screen root cause and no cleanup was performed.",
        "",
        "### Duplicate function definitions",
    ]
    for item in evidence["risks"]["duplicateFunctionDefinitions"]:
        report.append(f"- `{item['name']}`: lines {item['lines']}")
    report.append("\n### Repeated event-binding patterns")
    for item in evidence["risks"]["duplicateEventBindingPatterns"]:
        report.append(f"- `{item['target']}` ({item['count']} occurrences): " + ", ".join(str(o['line']) for o in item['occurrences']))
    report += [
        "",
        "## Root-cause assessment and gate",
        "",
        f"- **Static parser defect: {'present' if node_check['status'] == 'fail' else 'not present'}.** `node --check` reported the exact error above.",
        "- **Static black-screen candidate: present but not runtime-confirmed.** Because all three top-level views start with `hidden`, a parser failure before boot would leave them all hidden; a browser run is still required to prove the observed defect path.",
        "- Repeated function definitions and binding patterns remain follow-up risks only. They require runtime evidence (exception, ordering, or visibility-state corruption) before any cleanup or lifecycle change.",
        "- This task does not establish the six-path browser behavior, computed display/visibility/opacity, console errors, uncaught exceptions, resource errors, or hit testing.",
        "- **Next-step decision:** preservation may proceed as a baseline activity, but implementation must remain blocked until task 1 runtime evidence satisfies the design evidence gate and the syntax defect is addressed through the authorized implementation task. This report alone does not authorize an evidence-free broad refactor.",
    ]
    REPORT_PATH.write_text("\n".join(report) + "\n", encoding="utf-8")
    print(json.dumps({"syntax": node_check["status"], "node": node_check.get("version"), "checks": checks, "output": str(REPORT_PATH)}, ensure_ascii=False, indent=2))
    return 0 if node_check["status"] == "pass" and all(checks.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
