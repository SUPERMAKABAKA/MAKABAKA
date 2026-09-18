"""Dependency-free static/DOM-model exploration for the Nova black-screen bug.

This file is intentionally explicit about its boundary: the workspace has no
Node/QuickJS/browser runtime, so it cannot execute the ES2022 inline script.
It extracts and lexically checks the script, then simulates the six documented
lifecycle paths through the observed setView/enterApp/enterWelcome branches.
The output never treats the simulation as browser runtime evidence.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

SPEC_DIR = Path(__file__).resolve().parent
HTML_PATH = SPEC_DIR.parents[2] / "static" / "index.html"
EVIDENCE_PATH = SPEC_DIR / "exploration-evidence.json"
REPORT_PATH = SPEC_DIR / "exploration-report.md"


@dataclass
class ClassList:
    values: set[str] = field(default_factory=set)

    def toggle(self, name: str, force: bool | None = None) -> bool:
        next_value = (not (name in self.values)) if force is None else force
        if next_value:
            self.values.add(name)
        else:
            self.values.discard(name)
        return next_value

    def __str__(self) -> str:
        return " ".join(sorted(self.values))


@dataclass
class MiniElement:
    element_id: str
    base_display: str
    content: str
    interactive_count: int
    classes: ClassList = field(default_factory=lambda: ClassList({"hidden"}))
    style: dict[str, str] = field(default_factory=dict)

    @property
    def visible(self) -> bool:
        return (
            "hidden" not in self.classes.values
            and self.style.get("display") != "none"
            and self.style.get("visibility") != "hidden"
            and self.style.get("opacity") != "0"
        )

    @property
    def display(self) -> str:
        return "none" if not self.visible else self.style.get("display", self.base_display)


@dataclass
class MiniDOM:
    views: dict[str, MiniElement]
    body_front: bool = True

    @classmethod
    def create(cls) -> "MiniDOM":
        return cls(
            views={
                "welcomeScreen": MiniElement(
                    "welcomeScreen", "flex",
                    "Good choices start here. Your shopping companion, Nova. Start", 3,
                ),
                "authScreen": MiniElement(
                    "authScreen", "flex",
                    "Nova Sign in Create account Welcome back Username Password Sign in Back to home", 6,
                ),
                "appScreen": MiniElement(
                    "appScreen", "grid",
                    "Nova Shopping Assistant Ready to help you shop New chat Recent guest What are you looking for? Tell me what you need. Running shoes Coffee machine Headphones Camera Tell Nova what you're looking for", 8,
                ),
            }
        )

    def set_view(self, name: str) -> None:
        self.body_front = name != "app"
        for view_name, element in self.views.items():
            element.classes.toggle("hidden", view_name != {"welcome": "welcomeScreen", "auth": "authScreen", "app": "appScreen"}[name])

    def snapshot(self) -> dict[str, Any]:
        view_snapshots = []
        for element in self.views.values():
            view_snapshots.append({
                "id": element.element_id,
                "className": str(element.classes),
                "display": element.display,
                "visibility": element.style.get("visibility", "visible"),
                "opacity": element.style.get("opacity", "1"),
                "visible": element.visible,
                "visibleText": element.content if element.visible else "",
                "interactiveEntryCount": element.interactive_count if element.visible else 0,
            })
        return {
            "views": view_snapshots,
            "visibleTopLevelViewCount": sum(1 for item in view_snapshots if item["visible"]),
        }


def extract_script(html: str) -> str:
    scripts = re.findall(r"<script(?:\s[^>]*)?>([\s\S]*?)</script>", html, flags=re.I)
    if not scripts:
        raise ValueError("No inline script found")
    return "\n".join(scripts)


def lexical_syntax_check(source: str) -> dict[str, Any]:
    """Check delimiter/string/comment balance without claiming a JS parser.

    This catches truncated extraction and common parse damage. It is labelled
    heuristic because no ECMAScript parser is installed in this environment.
    """
    pairs = {"(": ")", "[": "]", "{": "}"}
    stack: list[tuple[str, int]] = []
    state = "code"
    quote = ""
    escaped = False
    regex_class = False
    line = 1
    i = 0
    errors: list[str] = []
    while i < len(source):
        char = source[i]
        nxt = source[i + 1] if i + 1 < len(source) else ""
        if char == "\n":
            line += 1
            if state == "line_comment":
                state = "code"
            if state == "string" and not escaped:
                errors.append(f"unterminated string at line {line - 1}")
                state = "code"
        if state == "line_comment":
            i += 1
            continue
        if state == "block_comment":
            if char == "*" and nxt == "/":
                state = "code"
                i += 2
                continue
            i += 1
            continue
        if state == "regex":
            if escaped:
                escaped = False
            elif char == "\\\\":
                escaped = True
            elif char == "[":
                regex_class = True
            elif char == "]":
                regex_class = False
            elif char == "/" and not regex_class:
                state = "code"
            i += 1
            continue
        if state == "string":
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                state = "code"
            i += 1
            continue
        if state == "template":
            # Treat a template as a string for balance purposes. The source
            # uses template literals, but nested ${} parsing is unnecessary
            # for this extraction-integrity check.
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == "`":
                state = "code"
            i += 1
            continue
        if char == "/" and nxt == "/":
            state = "line_comment"
            i += 2
            continue
        if char == "/" and nxt == "*":
            state = "block_comment"
            i += 2
            continue
        previous = source[:i].rstrip()[-1:] 
        if char == "/" and nxt not in "/*" and (previous in "=(:,[!&|?{;" or source[:i].rstrip().endswith("return")):
            state = "regex"
            regex_class = False
            escaped = False
            i += 1
            continue
        if char in "'\"`":
            state = "template" if char == "`" else "string"
            quote = char
            escaped = False
            i += 1
            continue
        if char in pairs:
            stack.append((char, line))
        elif char in pairs.values():
            if not stack or pairs[stack[-1][0]] != char:
                errors.append(f"unexpected {char!r} at line {line}")
            else:
                stack.pop()
        i += 1
    if state in {"string", "template", "block_comment"}:
        errors.append(f"unterminated {state}")
    errors.extend(f"unclosed {opening!r} from line {at_line}" for opening, at_line in stack)
    # No ECMAScript parser is installed. Keep the lexical result for debugging,
    # but do not label it as a syntax pass/fail because regex/template grammar
    # can produce false positives in this deliberately small scanner.
    return {
        "passed": None,
        "executed": False,
        "method": "not run: no ECMAScript parser/runtime installed",
        "lexicalHeuristicPassed": not errors,
        "lexicalHeuristicErrors": errors,
        "errors": [],
    }


def line_of(source: str, needle: str) -> int | None:
    match = re.search(re.escape(needle), source)
    return source.count("\n", 0, match.start()) + 1 if match else None


def function_definitions(source: str) -> dict[str, list[int]]:
    found: dict[str, list[int]] = {}
    for match in re.finditer(r"function\s+([A-Za-z_$][\w$]*)\s*\(", source):
        name = match.group(1)
        found.setdefault(name, []).append(source.count("\n", 0, match.start()) + 1)
    return found


def simulate_path(name: str) -> dict[str, Any]:
    storage = {}
    initial_hash = ""
    dom = MiniDOM.create()
    steps: list[str]
    expected = "welcomeScreen"
    runtime_exception = None
    if name == "first_open":
        steps = ["Clear nova_token and nova_user", "Open /"]
        dom.set_view("welcome")
    elif name == "direct_auth_hash":
        steps = ["Clear nova_token and nova_user", "Open /#/auth"]
        initial_hash = "#/auth"
        dom.set_view("auth")
        expected = "authScreen"
    elif name == "login_success":
        steps = ["Open /#/auth", "Enter alice / secret", "Submit Sign in"]
        initial_hash = "#/auth"
        dom.set_view("auth")
        storage = {"nova_token": "login-token", "nova_user": "alice"}
        dom.set_view("app")
        expected = "appScreen"
    elif name == "existing_token_boot":
        steps = ["Set nova_token=valid-token and nova_user=alice", "Cold-open /"]
        storage = {"nova_token": "valid-token", "nova_user": "alice"}
        dom.set_view("app")
        initial_hash = "#/app"
        expected = "appScreen"
    elif name == "app_refresh":
        steps = ["Set valid token and username", "Open /#/app", "Reload"]
        storage = {"nova_token": "valid-token", "nova_user": "alice"}
        initial_hash = "#/app"
        dom.set_view("app")
        expected = "appScreen"
    elif name == "logout_to_welcome":
        steps = ["Set valid token and username", "Open /#/app", "Click Sign out"]
        storage = {"nova_token": "valid-token", "nova_user": "alice"}
        initial_hash = "#/app"
        dom.set_view("app")
        storage = {}
        dom.set_view("welcome")
    else:
        raise ValueError(name)
    snapshot = dom.snapshot()
    expected_view = next(item for item in snapshot["views"] if item["id"] == expected)
    return {
        "path": name,
        "trigger": {
            "initialStorage": {"nova_token": "valid-token", "nova_user": "alice"} if name in {"existing_token_boot", "app_refresh", "logout_to_welcome"} else {},
            "simulatedFinalStorage": storage,
            "initialHash": initial_hash,
            "simulatedFinalHash": "" if name == "logout_to_welcome" else initial_hash,
        },
        "minimalReproduction": {
            "steps": steps,
            "expectedFinalView": expected,
            "harnessLimitations": [
                "No JavaScript engine was available, so this is a control-flow simulation, not execution of the inline script.",
                "No browser layout, paint, computed CSS cascade, resource loading, browser console, hit testing, or real network/SSE is available.",
            ],
        },
        "observation": {
            **snapshot,
            "expectedViewVisible": expected_view["visible"],
            "expectedViewHasContent": bool(expected_view["visibleText"]),
            "expectedViewHasInteractiveContent": expected_view["interactiveEntryCount"] > 0,
        },
        "runtime": {
            "executionAttempted": False,
            "executionBlockedReason": "No node, nodejs, deno, bun, quickjs, js2py, execjs, or esprima runtime is installed; cscript is legacy JScript and cannot parse this ES2022 source.",
            "executionError": None,
            "consoleErrors": None,
            "uncaughtExceptions": None,
            "unhandledRejections": None,
            "resourceErrors": None,
            "status": "blocked_runtime_not_executed",
        },
    }


def main() -> int:
    html = HTML_PATH.read_text(encoding="utf-8")
    source = extract_script(html)
    syntax = lexical_syntax_check(source)
    definitions = function_definitions(source)
    names = ["first_open", "direct_auth_hash", "login_success", "existing_token_boot", "app_refresh", "logout_to_welcome"]
    paths = [simulate_path(name) for name in names]
    static_facts = {
        "topLevelViewIds": ["welcomeScreen", "authScreen", "appScreen"],
        "hiddenRuleLine": line_of(html, ".hidden{display:none!important}"),
        "setViewLine": line_of(source, "function setView(name)"),
        "enterAppLine": line_of(source, "function enterApp()"),
        "enterWelcomeLine": line_of(source, "function enterWelcome()"),
        "bootLine": line_of(source, "if(token&&username){ enterApp(); }") or line_of(source, "if(token&&username)"),
        "duplicateFunctionDefinitions": {name: lines for name, lines in definitions.items() if len(lines) > 1},
    }
    evidence = {
        "generatedBy": "exploration_static_harness.py",
        "source": {
            "path": str(HTML_PATH.relative_to(SPEC_DIR.parents[2])),
            "inlineScriptSha256": hashlib.sha256(source.encode()).hexdigest(),
            "inlineScriptCharacters": len(source),
            "inlineScriptCount": len(re.findall(r"<script(?:\s[^>]*)?>", html, flags=re.I)),
        },
        "syntax": syntax,
        "staticFacts": static_facts,
        "harness": {
            "dependencyFree": True,
            "browserInstalledOrUsed": False,
            "javascriptExecutionAvailable": False,
            "model": "Python MiniDOM + lifecycle control-flow simulation",
            "limitations": [
                "The six paths were simulated from the observed source branches, not executed by an ECMAScript engine.",
                "A model-level unique visible view cannot establish actual browser visibility or black-screen behavior.",
                "Runtime exception, browser console, resource, computed-style, layout, and SSE fields are unknown (null), not passing.",
            ],
        },
        "paths": paths,
        "counterexamples": [],
        "classification": "blocked_no_runtime_evidence",
    }
    EVIDENCE_PATH.write_text(json.dumps(evidence, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    lines = [
        "# Bug-condition exploration evidence",
        "",
        "## Result",
        "**BLOCKED — no runtime evidence obtained.** The environment has no browser and no installed modern JavaScript runtime. The six paths below are MiniDOM control-flow simulations only; they must not be interpreted as passing or failing browser smoke checks.",
        "",
        f"- Source: `{evidence['source']['path']}`",
        f"- Inline script SHA-256: `{evidence['source']['inlineScriptSha256']}`",
        f"- Syntax extraction check: **NOT RUN** ({syntax['method']}); lexical heuristic: {'no obvious balance error' if syntax['lexicalHeuristicPassed'] else 'inconclusive/false-positive-prone'}",
        f"- Inline script characters: {len(source)}",
        "- Production files changed: none",
        "",
        "## Static facts",
        "",
        f"- Top-level nodes: `#welcomeScreen`, `#authScreen`, `#appScreen`; all are initially marked `hidden` in the source.",
        f"- `.hidden` rule line: {static_facts['hiddenRuleLine']}; `setView()` line: {static_facts['setViewLine']}; `enterApp()` line: {static_facts['enterAppLine']}; `enterWelcome()` line: {static_facts['enterWelcomeLine']}; boot branch line: {static_facts['bootLine']}.",
        "- Duplicate function names are recorded as risks only; this exploration does not infer causality from duplication.",
        "",
        "## Six-path simulated observations",
        "",
    ]
    for result in paths:
        observation = result["observation"]
        view_line = "; ".join(
            f"{view['id']}={'visible' if view['visible'] else 'hidden'} class=\"{view['className']}\" display={view['display']} visibility={view['visibility']} opacity={view['opacity']}"
            for view in observation["views"]
        )
        lines.extend([
            f"### {result['path']}",
            f"- Simulated trigger: `{json.dumps(result['trigger'], ensure_ascii=False)}`",
            f"- Simulated views: {view_line}",
            f"- Simulated visible top-level count: **{observation['visibleTopLevelViewCount']}**",
            f"- Simulated expected content/interactions: {observation['expectedViewHasContent']}/{observation['expectedViewHasInteractiveContent']}",
            f"- Runtime exception/console/resource status: **unknown — {result['runtime']['executionBlockedReason']}**",
            f"- Minimal reproduction: {' -> '.join(result['minimalReproduction']['steps'])}",
            "",
        ])
    lines.extend([
        "## Interpretation and next step",
        "",
        "The simulation reaches the expected unique-view branch for all six scenarios, but this is an **unobservable/unexpected-pass-like control-flow result**, not a successful exploration. Per the spec workflow, implementation must stop here: do not mark the bug as reproduced and do not infer that the defect is absent.",
        "",
        "To complete task 1, provide a browser or modern ECMAScript runtime (without installing dependencies if that is the constraint), or authorize an equivalent existing test runner. Required evidence remains computed display/visibility/opacity, visible and interactive content, console errors, `window.onerror`, `unhandledrejection`, resource failures, storage/hash state, and reproducible steps for each path.",
    ])
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"classification": evidence["classification"], "syntaxCheckExecuted": syntax["executed"], "lexicalHeuristicPassed": syntax["lexicalHeuristicPassed"], "paths": [{"path": item["path"], "simulatedVisibleCount": item["observation"]["visibleTopLevelViewCount"], "runtimeExecuted": item["runtime"]["executionAttempted"]} for item in paths]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
