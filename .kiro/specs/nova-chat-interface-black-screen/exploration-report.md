# Bug-condition exploration evidence

## Result
**BLOCKED — no runtime evidence obtained.** The environment has no browser and no installed modern JavaScript runtime. The six paths below are MiniDOM control-flow simulations only; they must not be interpreted as passing or failing browser smoke checks.

- Source: `static\index.html`
- Inline script SHA-256: `5999838d59fcfe8e575437aeee5af7abb11dfc5aee13e44243da70fb33e22160`
- Syntax extraction check: **NOT RUN** (not run: no ECMAScript parser/runtime installed); lexical heuristic: inconclusive/false-positive-prone
- Inline script characters: 72408
- Production files changed: none

## Static facts

- Top-level nodes: `#welcomeScreen`, `#authScreen`, `#appScreen`; all are initially marked `hidden` in the source.
- `.hidden` rule line: 631; `setView()` line: 35; `enterApp()` line: 155; `enterWelcome()` line: 60; boot branch line: 1221.
- Duplicate function names are recorded as risks only; this exploration does not infer causality from duplication.

## Six-path simulated observations

### first_open
- Simulated trigger: `{"initialStorage": {}, "simulatedFinalStorage": {}, "initialHash": "", "simulatedFinalHash": ""}`
- Simulated views: welcomeScreen=visible class="" display=flex visibility=visible opacity=1; authScreen=hidden class="hidden" display=none visibility=visible opacity=1; appScreen=hidden class="hidden" display=none visibility=visible opacity=1
- Simulated visible top-level count: **1**
- Simulated expected content/interactions: True/True
- Runtime exception/console/resource status: **unknown — No node, nodejs, deno, bun, quickjs, js2py, execjs, or esprima runtime is installed; cscript is legacy JScript and cannot parse this ES2022 source.**
- Minimal reproduction: Clear nova_token and nova_user -> Open /

### direct_auth_hash
- Simulated trigger: `{"initialStorage": {}, "simulatedFinalStorage": {}, "initialHash": "#/auth", "simulatedFinalHash": "#/auth"}`
- Simulated views: welcomeScreen=hidden class="hidden" display=none visibility=visible opacity=1; authScreen=visible class="" display=flex visibility=visible opacity=1; appScreen=hidden class="hidden" display=none visibility=visible opacity=1
- Simulated visible top-level count: **1**
- Simulated expected content/interactions: True/True
- Runtime exception/console/resource status: **unknown — No node, nodejs, deno, bun, quickjs, js2py, execjs, or esprima runtime is installed; cscript is legacy JScript and cannot parse this ES2022 source.**
- Minimal reproduction: Clear nova_token and nova_user -> Open /#/auth

### login_success
- Simulated trigger: `{"initialStorage": {}, "simulatedFinalStorage": {"nova_token": "login-token", "nova_user": "alice"}, "initialHash": "#/auth", "simulatedFinalHash": "#/auth"}`
- Simulated views: welcomeScreen=hidden class="hidden" display=none visibility=visible opacity=1; authScreen=hidden class="hidden" display=none visibility=visible opacity=1; appScreen=visible class="" display=grid visibility=visible opacity=1
- Simulated visible top-level count: **1**
- Simulated expected content/interactions: True/True
- Runtime exception/console/resource status: **unknown — No node, nodejs, deno, bun, quickjs, js2py, execjs, or esprima runtime is installed; cscript is legacy JScript and cannot parse this ES2022 source.**
- Minimal reproduction: Open /#/auth -> Enter alice / secret -> Submit Sign in

### existing_token_boot
- Simulated trigger: `{"initialStorage": {"nova_token": "valid-token", "nova_user": "alice"}, "simulatedFinalStorage": {"nova_token": "valid-token", "nova_user": "alice"}, "initialHash": "#/app", "simulatedFinalHash": "#/app"}`
- Simulated views: welcomeScreen=hidden class="hidden" display=none visibility=visible opacity=1; authScreen=hidden class="hidden" display=none visibility=visible opacity=1; appScreen=visible class="" display=grid visibility=visible opacity=1
- Simulated visible top-level count: **1**
- Simulated expected content/interactions: True/True
- Runtime exception/console/resource status: **unknown — No node, nodejs, deno, bun, quickjs, js2py, execjs, or esprima runtime is installed; cscript is legacy JScript and cannot parse this ES2022 source.**
- Minimal reproduction: Set nova_token=valid-token and nova_user=alice -> Cold-open /

### app_refresh
- Simulated trigger: `{"initialStorage": {"nova_token": "valid-token", "nova_user": "alice"}, "simulatedFinalStorage": {"nova_token": "valid-token", "nova_user": "alice"}, "initialHash": "#/app", "simulatedFinalHash": "#/app"}`
- Simulated views: welcomeScreen=hidden class="hidden" display=none visibility=visible opacity=1; authScreen=hidden class="hidden" display=none visibility=visible opacity=1; appScreen=visible class="" display=grid visibility=visible opacity=1
- Simulated visible top-level count: **1**
- Simulated expected content/interactions: True/True
- Runtime exception/console/resource status: **unknown — No node, nodejs, deno, bun, quickjs, js2py, execjs, or esprima runtime is installed; cscript is legacy JScript and cannot parse this ES2022 source.**
- Minimal reproduction: Set valid token and username -> Open /#/app -> Reload

### logout_to_welcome
- Simulated trigger: `{"initialStorage": {"nova_token": "valid-token", "nova_user": "alice"}, "simulatedFinalStorage": {}, "initialHash": "#/app", "simulatedFinalHash": ""}`
- Simulated views: welcomeScreen=visible class="" display=flex visibility=visible opacity=1; authScreen=hidden class="hidden" display=none visibility=visible opacity=1; appScreen=hidden class="hidden" display=none visibility=visible opacity=1
- Simulated visible top-level count: **1**
- Simulated expected content/interactions: True/True
- Runtime exception/console/resource status: **unknown — No node, nodejs, deno, bun, quickjs, js2py, execjs, or esprima runtime is installed; cscript is legacy JScript and cannot parse this ES2022 source.**
- Minimal reproduction: Set valid token and username -> Open /#/app -> Click Sign out

## Interpretation and next step

The simulation reaches the expected unique-view branch for all six scenarios, but this is an **unobservable/unexpected-pass-like control-flow result**, not a successful exploration. Per the spec workflow, implementation must stop here: do not mark the bug as reproduced and do not infer that the defect is absent.

To complete task 1, provide a browser or modern ECMAScript runtime (without installing dependencies if that is the constraint), or authorize an equivalent existing test runner. Required evidence remains computed display/visibility/opacity, visible and interactive content, console errors, `window.onerror`, `unhandledrejection`, resource failures, storage/hash state, and reproducible steps for each path.
