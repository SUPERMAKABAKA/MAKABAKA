# Technical Design: Nova Chat Interface Redesign

## Overview

This change redesigns only the authenticated chat view inside `static/index.html`. It replaces the persistent history sidebar with a top-navigation history drawer, applies a warm off-white monochrome editorial visual system, preserves inline recommendation rendering, and prevents recommendations from opening the shopping browser until a shopper activates a card.

The implementation remains a single-file, dependency-free HTML/CSS/JavaScript frontend. The existing authentication code, `POST /chat/stream` SSE contract, backend Python, routes, agents, prompts, recommendation data, and recommendation ranking are unchanged.

The following values match the revised `Approved_Chat_Copy` in `requirements.md`:

- Headline: **“What are you looking for?”**
- Supporting text: **“Tell me what you need. I’ll help narrow the options and find what fits you best.”**
- Composer placeholder: **“Tell Nova what you're looking for...”**
- Suggestion chips, in order: **“Running shoes”**, **“Coffee machine”**, **“Headphones”**, **“Camera”**

## Scope and Change Boundary

### Allowed edit surface

Only the authenticated app blocks in `static/index.html` may change:

1. The CSS section beginning at `/* ===== APP ===== */`, plus app-only responsive and reduced-motion rules.
2. The DOM subtree rooted at `#appScreen`.
3. The chat JavaScript beginning at `/* ---- chat ---- */`, including session, history, composer, product-panel, Nova-assistant, and render functions.
4. Shared helpers such as `$`, `esc`, `sleep`, `prefersReduced`, and existing authenticated-view references may be called but not behaviorally changed.

### Protected surface

The following must not be edited:

- `#welcomeScreen` and its `.welcome-page` descendants
- `#authScreen` and its `.auth` descendants
- welcome/auth CSS and canvas/hero JavaScript
- auth state, auth form handlers, storage keys, and `/auth/*` requests
- Python files, APIs, routes, agent code, prompts, and recommendation logic
- the request/response shape or URL of `POST /chat/stream`

Spec creation changes only `.kiro/specs/nova-chat-interface-redesign/*`. Later implementation limits production app changes to authenticated portions of `static/index.html`. Development and test artifacts may be created for validation.

## Architecture

```text
#appScreen
├── .chat-shell
│   ├── .topbar (ChatTopNavigation)
│   │   ├── .topbar-brand (Nova / Shopping Assistant)
│   │   ├── #topMeta
│   │   └── .topbar-actions
│   │       ├── #newChat
│   │       ├── #sideToggle (Recent conversations)
│   │       └── #profileControl + #profileMenu
│   ├── #stream > #streamInner
│   │   ├── #welcome (empty state)
│   │   └── generated .msg nodes
│   └── .composer > #input + #send
├── #historyBackdrop
├── #historyDrawer
│   ├── #historyClose
│   └── #hist (existing history container)
├── #productPanel (existing browser panel)
├── #novaBuddy
└── #nbPanel
```

The app shell has no persistent left column. On desktop it uses a two-column layout: centered chat content plus a zero-width or open product panel. `#historyDrawer` overlays the chat from the left and never consumes a permanent grid column. On tablet and mobile, both history and shopping surfaces overlay the chat.

### CSS isolation strategy

Authenticated-chat design tokens are declared on `#appScreen`, not `:root`:

```css
#appScreen {
  --chat-bg: #f7f7f4;
  --chat-surface: #ffffff;
  --chat-surface-muted: #f0f1f2;
  --chat-ink: #111111;
  --chat-ink-muted: #62666b;
  --chat-line: #d9dce0;
  --chat-focus: #3f444a;
  --chat-shadow: 0 8px 16px rgba(17, 17, 17, .10);
  --chat-content: 840px;
  --chat-duration: 180ms;
}
```

Every new or replaced rule is rooted at `#appScreen`, for example `#appScreen .topbar`, `#appScreen .rec`, and `#appScreen #input`. No new global `body`, `textarea`, `button`, `.welcome`, `.auth`, `:root`, `.ambient`, or `.grain` rule is permitted. `#appScreen` itself supplies an opaque background so the existing global ambient layer cannot show through; hiding or retheming the shared ambient elements is unnecessary.

Existing broad app rules that could leak, such as unqualified `textarea`, are replaced in the authenticated block with app-rooted selectors. Existing welcome/auth rules and their `--n-*` tokens remain byte-for-byte unchanged. Solid fills replace app gradients and glass effects. Standard borders remain `1px`; shadows use at most `16px` blur and `0.10` alpha.

## Components and Interfaces

### Components and Selector Boundaries

### 1. Chat top navigation

**Boundary:** `#appScreen .topbar`

The top navigation contains:

- `.topbar-brand`: visible `Nova` identity and `Shopping Assistant` title.
- `#topMeta`: existing status node, retained for short neutral session/result status.
- `#newChat`: moved from the sidebar into navigation; ID and click behavior remain.
- `#sideToggle`: moved into navigation and renamed visually to Recent; `aria-label="Recent conversations"`, `aria-controls="historyDrawer"`, and synchronized `aria-expanded`.
- `#profileControl`: avatar/name button using the existing `#userAv` and `#userName` nodes.
- `#profileMenu`: a quiet popover containing existing `#logout`. The existing logout handler and auth behavior remain unchanged.

Desktop shows text labels where space allows. Tablet/mobile may hide nonessential visible button text while retaining accessible names. All primary icon-only controls are at least `44px × 44px`.

### 2. History drawer

**Boundary:** `#historyBackdrop`, `#historyDrawer`, `#historyClose`, and existing `#hist`

The persistent `.side` layout is removed. The drawer is an app-local overlay with a solid white surface, one-pixel border, and low-elevation shadow. Recommended semantics:

```html
<div id="historyBackdrop" hidden></div>
<aside id="historyDrawer" role="dialog" aria-modal="true"
       aria-labelledby="historyTitle" aria-hidden="true">
  <header>…<button id="historyClose" aria-label="Close recent conversations">…</button></header>
  <div class="hist" id="hist" role="list"></div>
</aside>
```

History entries become native `<button type="button" class="hist-item">` controls. `pushHistory` continues to prepend, so the DOM is reverse chronological without changing the session store. The active entry receives `.on` and `aria-current="true"`; all others omit `aria-current`.

`openHistoryDrawer()` records `#sideToggle` as opener, removes `hidden` from the backdrop, sets `aria-hidden="false"` and `aria-expanded="true"`, adds `history-open` to `#appScreen`, then focuses the active history entry or `#historyClose` when no entry exists. `closeHistoryDrawer()` reverses those states and returns focus to the recorded opener.

The drawer closes on:

- `#historyClose` activation
- backdrop activation
- `Escape`
- history-entry activation, after `switchToSession(id)`
- new-chat activation if the drawer was open
- logout/view departure

While open, Tab and Shift+Tab cycle among the drawer’s focusable controls. Background content is visually covered by the backdrop and is excluded from sequential interaction using `inert` when supported; the focus trap remains the fallback.

### 3. Empty state

**Boundary:** `#welcome` inside `#streamInner`

The node ID is retained because existing new-chat/session code moves this node. Decorative `#welcomeFx` and `#welcomeOrb` content is removed from the authenticated empty state; its associated authenticated-only visual startup calls become safe no-ops or are no longer called from chat transitions. This prevents idle decorative motion without touching landing-page hero code.

The empty state contains the authoritative exact copy and four native suggestion buttons. Chips use `<button type="button" class="chip">`, not spans. Activating a chip while idle assigns its exact label to `#input` and immediately calls `doSend()`. When `busy === true`, chips are disabled or ignored consistently with other submission controls.

### 4. Conversation stream and messages

**Boundary:** `#stream`, `#streamInner`, generated `.msg`, `.bubble`, `.react`, `.opts`, `.recs`, and `.notices`

`#streamInner` is the single content column and uses `width:min(100%, var(--chat-content))`, where `--chat-content` is `840px`. At desktop widths it remains centered while the product panel is closed.

- `.msg.user`: right aligned; black solid bubble and off-white text.
- `.msg.ai`: left aligned; white/transparent editorial treatment with visible Nova mark/name.
- `.thinking`: neutral sentence-case copy such as `Nova is reviewing your request…`; no orbit, sheen, or continuously animated decoration. A static mark may remain.
- `.tok`: tokens appear without blur animation; event order remains controlled by `appendToken`.
- `.caret`: a restrained text cursor may blink only while streaming. Under reduced motion it is static.
- `.react`: solid muted surface with explicit Thought, Plan, and Action labels.
- `.notice`: muted inline status associated with the same response.

All generated user/service text continues to use `textContent` or `esc()` before `innerHTML` insertion.

### 5. Composer

**Boundary:** `#appScreen .composer`, `.composer-inner`, `.input-wrap`, `#input`, and `#send`

The composer remains at the bottom of `.main`, visually floating over the off-white page with a white solid fill, one-pixel border, rounded shape, and low-elevation shadow. It does not add a plus control; Requirement 4.8 therefore remains non-applicable and no unsupported attachment affordance is introduced.

`#input` keeps autosizing up to `140px` and uses the exact placeholder `Tell Nova what you're looking for...`. `#send` is a circular black `44px × 44px` button with a light directional icon and an explicit `aria-label="Send message"`.

Submission rules remain centralized in `doSend()`:

- whitespace-only input: disabled and no request
- Enter without Shift: prevent newline and submit once when idle
- Shift+Enter: preserve native newline and do not submit
- Send button: submit once when idle
- chip/quick option: place exact text in input, then route through `doSend()`

`syncSendState()` becomes the single expression of `send.disabled = busy || !input.value.trim()` and is called after input, busy, send, failure, and reset transitions.

### 6. Recommendations and shopping browser

**Boundary:** `renderRecs`, `.recs`, `.rec`, `openRecommendationsPanel`, `selectProduct`, `closeProduct`, and `#productPanel`

Recommendation title, rank, reason, positives, negatives, source ordering, and SSE payload handling remain unchanged. Cards become native buttons or keyboard-equivalent controls with `data-rec-index`, an accessible label, and visible focus styling.

The only recommendation-arrival behavior removed is this tail effect from `renderRecs`:

```js
// Remove: automatic first-card selection and panel opening.
if (recs.length) {
  cards[0]?.classList.add("active");
  activeRecCard = cards[0] || null;
  openRecommendationsPanel(recs);
}
```

`renderRecs()` ends after appending inline cards/notices and scrolling. It must not set `.active`, `activeRecCard`, `.panel-open`, `aria-hidden="false"`, an iframe URL, or a selected product tab.

On explicit card activation:

1. Clear `.active`/`aria-pressed` from sibling recommendation cards.
2. Set the activated card as `activeRecCard` and record it as `productPanelOpener`.
3. Call `openRecommendationsPanel(recs)` to construct product tabs.
4. Call `selectProduct(index)` so the clicked card—not always index zero—is selected.
5. Set `#productPanel[aria-hidden="false"]` and focus `#ppClose` after the panel becomes visible.

`closeProduct({restoreFocus = true})` preserves the existing iframe cleanup, removes `.panel-open`, sets `aria-hidden="true"`, clears the active card state, and returns focus to the activating card when it remains connected. Session switch and new chat call it with focus handoff appropriate to their own destination.

The existing AliExpress iframe behavior, Amazon external link, `EMBED_FW`, `fitEmbed`, product tabs, and drag formula remain. Desktop drag width remains:

```js
Math.max(300, Math.min(window.innerWidth - 320, window.innerWidth - pointerX))
```

The resize handle receives separator semantics (`role="separator"`, vertical orientation, current/min/max values). Existing pointer/touch behavior is retained; optional ArrowLeft/ArrowRight support changes width in small increments without changing limits.

### 7. Session behavior

**Boundary:** `sessions`, `sessionId`, `saveSession`, `pushHistory`, `switchToSession`, and `#newChat` handler

The existing in-memory model remains proportionate to the single-file app:

```js
// sessionId -> snapshot
sessions = {
  [sessionId]: {
    title: string, // first shopper message, truncated for display only
    html: string   // #streamInner snapshot
  }
}
```

No local/session storage is added for conversations. Reload therefore retains existing memory-only initialization behavior.

`pushHistory(text)` is called only when the active session has no entry. It creates one button, stores the unmodified current snapshot, prepends the entry, and marks only it active. New-chat IDs continue to use `newId()`; each activation creates a fresh ID, resets the stream to `#welcome`, clears active history treatment, closes drawer/product surfaces, resets top metadata, and focuses `#input`. Empty sessions do not enter `sessions` or `#hist`.

`saveSession()` still snapshots the current conversation whenever content settles. To keep restored interactive descendants operable despite `innerHTML` restoration, interactions for `.rec` and `.opt` use event delegation from `#streamInner` and stable `data-*` attributes, or `switchToSession()` calls a single `rehydrateConversationInteractions()` after restoring HTML. Delegation is preferred because it avoids serializing listeners and minimizes code.

`switchToSession(id)` performs the following atomic transition:

1. Reject an unknown ID without changing state.
2. Save the current represented session, if any.
3. Set `sessionId = id` and restore `sessions[id].html`.
4. Re-establish active history state (`.on`, `aria-current`).
5. Close the shopping panel and history drawer.
6. Restore default top metadata, scroll to the latest content, and leave focus on the history opener after drawer closure.

### 8. Floating Nova assistant

**Boundary:** `#novaBuddy`, `#nbPanel`, `.nb-quick`, and `#nbNewChat`

The assistant remains available but becomes a quiet monochrome circular/rounded control no larger than necessary for a `44px` target. Continuous bob, glow, pulse, orbit, arm, blink, and idle movement are removed. Busy/happy state may change a static icon or label but cannot introduce continuous motion.

`#novaBuddy` becomes a native button where practical, with `aria-controls="nbPanel"` and synchronized `aria-expanded`. `#nbPanel` retains dialog semantics and receives synchronized `aria-hidden`. Opening focuses its first quick action; Escape, outside activation, or an action closes it. Close returns focus to `#novaBuddy`; a selected quick action then follows the normal submission focus lifecycle. `#nbNewChat` delegates to `#newChat.click()` exactly as today.

## Data Models

### State Model and Transitions

### State variables

```js
{
  sessionId: string,
  sessions: Record<string, {title: string, html: string}>,
  busy: boolean,
  historyOpen: boolean,       // represented by #appScreen.history-open
  profileOpen: boolean,       // represented by #profileMenu hidden/ARIA state
  buddyPanelOpen: boolean,    // represented by #nbPanel.open
  productPanelOpen: boolean,  // represented by #appScreen.panel-open
  activeRecCard: Element|null,
  historyOpener: Element|null,
  productPanelOpener: Element|null
}
```

### Transition table

| Event | Preconditions | State/result | Focus result |
|---|---|---|---|
| Open recent | authenticated app visible | drawer open, active session marked | active entry, else drawer close |
| Close recent / Escape / backdrop | drawer open | drawer closed | `#sideToggle` |
| Select history entry | known session | save current, restore selected, close product and drawer | `#sideToggle` |
| New chat | any non-auth-busy app state | fresh ID, empty state, no history entry, panels closed | `#input` |
| Submit | trimmed input and `busy === false` | `busy=true`, user message and loading state rendered, one SSE request | input restored after settle |
| Receive token | active request | append token to active response in order | unchanged |
| Receive recommendations | active response | inline cards only | unchanged |
| Activate recommendation | valid card | panel open, clicked product/card active | `#ppClose` |
| Close product | panel open | iframe cleared, no active card | activating recommendation card |
| Open Nova quick panel | panel closed | quick panel open and identified | first quick action |
| Close Nova quick panel | panel open | quick panel closed | `#novaBuddy` |
| Request failure | request active | Nova error bubble, `busy=false`, controls synchronized | `#input` |

Only one lightweight overlay menu/drawer should be open at a time: opening history closes profile and Nova quick panels; opening profile or Nova quick panel closes the other lightweight surfaces. The shopping browser may coexist with neither history drawer nor profile/quick popovers; opening it closes those overlays.

## Interfaces

### Existing service contract (unchanged)

```js
fetch("/chat/stream", {
  method: "POST",
  headers: {
    "Content-Type": "application/json",
    ...(token ? { Authorization: `Bearer ${token}` } : {})
  },
  body: JSON.stringify({ session_id: sessionId, message: text })
});
```

The parser continues to recognize:

```js
{ event: "token", data: { text: string } }
{ event: "recommendations", data: {
    react_steps?: Array<{thought?: string, plan?: string, action?: string}>,
    recommendations?: Array<{
      product_id?: string,
      title?: string,
      reason?: string,
      summary?: { positives?: string[], negatives?: string[] }
    }>,
    options?: string[],
    notices?: string[],
    status?: string
} }
{ event: "error", data: { error?: string } }
```

No server event, field, ordering rule, authorization behavior, route, or payload is changed.

### App-local controller functions

```js
openHistoryDrawer(): void
closeHistoryDrawer({restoreFocus = true} = {}): void
syncSendState(): void
openProfileMenu(): void
closeProfileMenu({restoreFocus = true} = {}): void
openRecommendationsPanel(recs: Recommendation[]): void
selectProduct(index: number): void
closeProduct({restoreFocus = true} = {}): void
setBuddyPanel(open: boolean, {restoreFocus = true} = {}): void
rehydrateConversationInteractions?(): void
```

These are local functions in the existing script, not exported modules or new APIs.

## Error Handling

- Unknown session ID: `switchToSession` returns without changing `sessionId`, DOM, drawer, or focus.
- Empty/whitespace submission: `doSend` returns before state mutation or fetch.
- Repeated submission while busy: all sources route through the same `busy` guard; option groups also retain `.done`/disabled state.
- Non-successful response or missing response body: remove loading state, render `Sorry, the request failed. Please try again.` inside a Nova response, then execute common cleanup.
- Connection/read failure: render `Network error. Please check the server and retry.`, set `busy=false`, synchronize controls, and focus input.
- Malformed SSE JSON: retain the existing defensive empty-data behavior; no script exception should escape the stream loop.
- Empty recommendations: do not open the browser, build tabs, or change active recommendation state.
- Invalid product index: `selectProduct` returns without changing iframe or active tab.
- Detached product opener: product close skips focus restoration rather than throwing.
- Missing optional browser APIs (`ResizeObserver`, `inert`, `visualViewport`): retain current resize/window and focus-trap fallbacks.

Common request cleanup remains in `finally` so composer recovery occurs for success, HTTP failure, SSE error, and thrown connection errors.

## Accessibility

- Use native buttons for history entries, suggestion chips, clarification chips, recommendation cards, top-nav actions, and the Nova assistant.
- Preserve visible text or `aria-label` for every icon-only control.
- Use `aria-expanded` + `aria-controls` on drawer/profile/quick-panel openers and synchronized `aria-hidden` on closable surfaces.
- Mark the history drawer as a labelled modal dialog; mark the shopping panel as a labelled complementary region or dialog according to its overlay mode.
- Use `aria-current="true"` for the active conversation and `aria-pressed="true"` for the active recommendation/clarification selection where applicable.
- Add an app-local polite live status node or apply `role="status"` to loading status. Errors remain inside a visible Nova response and may use `role="alert"` without duplicating content.
- Provide a `2px` high-contrast focus outline with sufficient offset. The dark outline against white and inverse outline against black controls must meet 3:1 non-text contrast.
- Primary icon targets are at least `44px × 44px`; text buttons have at least a `44px` block-size where they are primary navigation actions.
- Drawer, profile, quick panel, and product panel restore focus to their opener on close. Action-triggered transitions may subsequently move focus to `#input` only as part of the established send/new-chat completion.
- Escape closes the topmost open drawer/menu/panel without affecting conversation state.
- Generated recommendation and option controls remain keyboard-activatable after session restoration through native controls and event delegation.

## Responsive Design

### Desktop: `min-width: 1024px`

- `#streamInner` and `.composer-inner` share an `840px` maximum width and remain centered while `#productPanel` is closed.
- Major content groups use at least `24px` vertical spacing.
- History drawer width is approximately `320px` and overlays from the left.
- Product panel remains a right grid column with existing `300px` minimum and `window.innerWidth - 320px` maximum drag limits.
- Top navigation displays brand, title, metadata, and labeled actions.

### Tablet: `768px–1023px`

- Top navigation uses compact gaps and may hide `#topMeta` before hiding action labels.
- All actions remain visible and keyboard/touch reachable without horizontal document scrolling.
- History drawer overlays with `width:min(320px, calc(100vw - 24px))`.
- Product panel overlays from the right rather than reducing chat width.

### Mobile: `<768px`

- App, stream, navigation, and composer use `max-width:100%` and `min-width:0`; recommendation summaries collapse to one column.
- Navigation keeps Nova identity plus compact New chat, Recent, and Profile controls; accessible names remain unchanged.
- History drawer uses `width:min(100vw, 340px)` and never exceeds the visual viewport.
- Product panel uses `inset:0` or `width:100vw`; its header and close button remain sticky/visible, and product tabs/content remain scrollable.
- The composer uses safe-area padding (`env(safe-area-inset-bottom)`) and remains in the app flex layout rather than fixed over messages. The stream has enough bottom spacing for the composer and scrolls the latest message into view.
- `100dvh` is the primary height. If `window.visualViewport` exists, its `resize` event schedules `scrollDown()` while the input is focused so an on-screen keyboard resize does not hide the latest message.
- The floating assistant is offset above the composer/safe area and reduced visually without reducing its `44px` hit target.

## Motion

Standard hover/focus/open/close transitions use `180ms`, within the required `120–240ms` range. There is no continuous app idle animation. Message/card entry motion is a short one-shot opacity transition only.

Under `@media (prefers-reduced-motion: reduce)`, app-scoped animations are disabled, smooth scrolling becomes automatic scrolling, panel/drawer translation is removed, and state changes use immediate opacity/visibility changes. The existing global reduced-motion behavior is not expanded or changed for protected surfaces.

## Correctness Properties

The prework identified renderer, ordering, state-machine, and clamping behaviors as suitable for property tests. During property reflection, overlapping checks were consolidated: history ordering and entry cardinality form one registry property; session snapshot/restoration and active identification form one round-trip property; recommendation activation/update/close form one selection-lifecycle property; and Enter/button submission share one gating property. Visual, fixed-copy, responsive, accessibility, infrastructure, and protected-surface criteria remain example, smoke, or integration tests rather than artificial randomized properties.

### Property 1: History exactly represents messaged sessions in reverse chronology

For any sequence of newly created sessions in which any subset receives one or more valid shopper messages, the history drawer contains exactly one entry for each session that received a first message, contains no entry for an empty session, and orders represented sessions from most recently created entry to least recently created entry.

**Validates: Requirements 3.7, 7.1, 7.7**

### Property 2: Session snapshot round trip preserves supported conversation content

For any two or more valid in-memory conversation sessions containing arbitrary combinations of shopper messages, Nova messages, ReAct details, clarification options, recommendation cards, and notices, saving a session, switching away, and switching back restores equivalent visible content, identifies exactly the restored session as active, and keeps restored controls operable.

**Validates: Requirements 3.8, 3.12, 7.2, 7.3**

### Property 3: Session changes close product browsing

For any valid source and target conversation sessions and any selected recommendation in the source session, switching sessions or creating a new session leaves the shopping browser closed, clears active recommendation treatment, and does not change the selected target session snapshot.

**Validates: Requirements 6.10, 7.6**

### Property 4: Submission is gated and trigger-independent

For any composer string and either supported primary trigger (Enter without Shift or Send activation), exactly one chat submission occurs if and only if the string contains non-whitespace content and the interface is not busy; otherwise no submission occurs and the Send control remains disabled for whitespace-only or busy states.

**Validates: Requirements 4.10, 4.11, 4.13**

### Property 5: Stream tokens preserve event order

For any finite sequence of valid token event strings, including empty strings, whitespace, punctuation, and Unicode, rendering the sequence produces response text equal to the concatenation of token text in emission order.

**Validates: Requirements 5.4**

### Property 6: Structured response renderers preserve payload content

For any valid arrays of ReAct steps, clarification options, and notices, rendering the response displays every Thought, Plan, and Action value under its corresponding label and displays every option and notice exactly once, safely escaped, in source order within the associated Nova response.

**Validates: Requirements 5.5, 5.6, 5.10**

### Property 7: Clarification groups permit at most one submission

For any non-empty clarification option group and any activation sequence while the interface transitions from idle to busy, the first accepted option is displayed as the sole selected option and its exact label is submitted once, while all later activations from that group cause no additional submission.

**Validates: Requirements 5.7, 5.8, 5.9**

### Property 8: Recommendation arrival is inline and non-interrupting

For any valid recommendation array and initially closed shopping browser, rendering recommendations creates one inline card per recommendation in source order with matching title, rank, reason, positive summary, and negative summary, while leaving the browser closed and leaving every card inactive.

**Validates: Requirements 6.1, 6.2, 6.3**

### Property 9: Recommendation selection follows the last explicit activation

For any non-empty recommendation array and any valid sequence of card indices, each explicit card activation opens the shopping browser and makes exactly that card/product active; after the final activation the panel represents the final index, and closing the panel leaves it hidden with no active card.

**Validates: Requirements 6.4, 6.5, 6.6, 6.9**

### Property 10: Product-panel resizing is clamped

For any Desktop_Viewport width and any pointer position used during a resize gesture, the computed product-panel width equals the existing clamp formula and remains between `300px` and `window.innerWidth - 320px` whenever that interval is valid.

**Validates: Requirements 6.8**

### Property 11: New-chat identifiers are unique within the active runtime

For any finite sequence of New Chat activations in one page runtime, each generated conversation identifier differs from every still-registered session identifier and the newly active empty session has no history entry until its first valid message submission.

**Validates: Requirements 7.4, 7.7**

## Testing Strategy

### Unit and property tests

Use a lightweight DOM harness around the existing inline functions with mocked `fetch`, stream reader, focus, and geometry. No production dependency is added. Property tests run at least 100 generated cases per property and include this traceability label:

`Feature: nova-chat-interface-redesign, Property {number}: {property title}`

Property generators emphasize:

- whitespace and Unicode composer strings
- token arrays with punctuation, line breaks, and Unicode
- session sequences with empty/messaged sessions and mixed rendered content
- recommendation arrays of varying lengths and explicit non-first selections
- repeated clarification activations
- desktop viewport/pointer widths around clamp boundaries

Example-based unit tests cover exact copy, Shift+Enter, error branches, ARIA state synchronization, Escape/backdrop dismissals, and focus restoration. Property tests are not used for visual layout, external iframe behavior, protected views, or host configuration.

### Static checks

1. Parse `static/index.html` for balanced/valid structure.
2. Extract the embedded script and run a JavaScript syntax check.
3. Run Python compile checks without modifying Python files.
4. Inspect the diff to confirm no protected DOM/CSS/JS sections or backend files changed.
5. Search `renderRecs` to ensure recommendation-arrival code contains no call to `openRecommendationsPanel` outside an explicit card activation path.

### Browser and integration checks

Run the existing host and authenticate through the unchanged flow, then verify:

- no uncaught page exception or console error
- one `/chat/stream` submission and ordered token rendering
- muted loading, HTTP failure, and connection recovery states
- suggestion and clarification submission paths
- recommendation arrival leaves a closed panel closed
- activating a non-first recommendation opens/selects that recommendation
- panel close, external link, iframe, and desktop resizing
- two-session creation, drawer ordering, switching, restored structured content, and new chat
- keyboard-only use of composer, top navigation, drawer, profile, clarification, recommendations, product close, and Nova quick panel
- focus return from every closable surface
- reduced-motion behavior

### Responsive matrix

Validate at the required viewport sizes:

- `1440 × 900`: centered `840px` content, desktop drawer, resizable product column
- `834 × 1112`: all top-nav actions reachable, overlay panels, no horizontal page scroll
- `390 × 844`: full-width content/panels, visible close controls, safe composer, no horizontal page scroll

Also resize the mobile visual viewport while `#input` is focused to emulate an on-screen keyboard and confirm the latest message and composer remain reachable.

### Protected-surface regression

Capture or compare landing, login, and registration views before and after the implementation at representative desktop/mobile sizes. Run the existing auth and Python tests. The accepted diff must show no changes to auth JavaScript, backend Python, APIs, routes, agent code, prompts, or recommendation output logic.
