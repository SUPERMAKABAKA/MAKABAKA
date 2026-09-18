# Task 4.1 expected-behavior report

## Result

**Static expected-behavior PASS; browser/runtime BLOCKED.** The original task 1 `exploration_static_harness.py` was rerun without changing it into a new pass-only test. Its six MiniDOM control-flow scenarios each reached exactly one modeled visible top-level view with modeled content and interactive entries. This is a static/control-flow expectation only, not a browser smoke pass.

No production file was modified by task 4.1. Evidence is recorded in `task4.1-expected-behavior-evidence.json`.

## Validation commands

- `exploration_static_harness.py`: completed; classification remains `blocked_no_runtime_evidence`.
- `task2_static_check.py`: **PASS, 11/11**.
- `task3_preservation_check.py`: **static PASS, 58/58 source contracts and 5/5 protected structure**; runtime remains blocked.
- Node syntax check on the current extracted inline script: **PASS**, Node `v24.19.0`, return code `0`, no stderr.
  - Command: `C:\\Program Files\\nodejs\\node.exe --check .kiro/specs/nova-chat-interface-black-screen/task3-inline-script.js`

## Six-path modeled results

| Path | Storage/hash trigger and final state | Expected modeled view | Visible count | Modeled content/interaction |
|---|---|---|---:|---|
| `first_open` | empty storage / empty hash -> empty storage / empty hash | `welcomeScreen` | 1 | pass |
| `direct_auth_hash` | empty storage / `#/auth` -> empty storage / `#/auth` | `authScreen` | 1 | pass |
| `login_success` | empty storage, `#/auth` -> `nova_token=login-token`, `nova_user=alice`, hash remains `#/auth` in harness model | `appScreen` | 1 | pass |
| `existing_token_boot` | valid token/user, `#/app` -> unchanged valid token/user, `#/app` | `appScreen` | 1 | pass |
| `app_refresh` | valid token/user, `#/app` -> unchanged valid token/user, `#/app` | `appScreen` | 1 | pass |
| `logout_to_welcome` | valid token/user, `#/app` -> empty storage, empty hash | `welcomeScreen` | 1 | pass |

The complete per-view class/display/content snapshots, trigger steps, and storage/hash values are in the JSON evidence. The harness still reports its known limitation: it does not execute the inline ES2022 script or render a browser.

## Counterexample status

The task 4 pre-fix counterexample has disappeared in the available static check:

- Before the quote-boundary fix: `SyntaxError: Unexpected identifier 'insufficient'` at extracted script line 520 (HTML line 1622).
- After the fix: Node `--check` returns `0` with no stderr.
- Because all top-level views initially carry `hidden`, the parse failure was a strong static black-screen candidate. Its disappearance supports static expected restoration, but browser causality is still not proven.

No new browser counterexample can be classified because no browser was available. The harness's `counterexamples` list is empty for this static rerun; this must not be interpreted as proof that the production defect is absent in a real browser.

## Runtime boundary

The following remain **unavailable**, not passing: computed CSS/display/visibility/opacity, paint/layout and hit testing, browser console errors, `window.onerror`, `unhandledrejection`, resource errors, real storage/hash transitions, network requests, SSE, and actual six-path interaction. The only executable syntax validation is Node parsing; the harness itself does not execute JavaScript.

Duplicate function definitions and event-binding patterns remain unconfirmed risks. No cleanup or unrelated production change was made.

## Handoff

Task 4.1 is complete with the required static expected-behavior result and explicit runtime limitation. **Tasks 4.2 and 4.3 are allowed to proceed**, with 4.2 retaining the same runtime limitation and 4.3 auditing the implementation decision and diff boundary.
