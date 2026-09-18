# Implementation Plan: Nova Chat Interface Redesign

## Overview

Redesign only the authenticated chat portions of `static/index.html` as a dependency-free HTML/CSS/JavaScript interface. Preserve the existing IDs, in-memory history/session model, `/chat/stream` SSE contract, authentication behavior, protected landing/login/register presentation, backend, routes, agents, prompts, and recommendation output/ranking. This specification-creation update changes only `.kiro/specs/nova-chat-interface-redesign/`; during later implementation task execution, production application changes remain limited to authenticated portions of `static/index.html`, while development and test artifacts required for validation are permitted. Implementation proceeds incrementally from app-scoped structure and styling through behavior-preserving component restyling, explicit recommendation activation, accessibility, responsive behavior, and focused validation.

## Tasks

- [x] 1. Establish the app-scoped visual system and history drawer shell
  - [x] 1.1 Add authenticated-app design tokens and foundational layout styles
    - Define warm off-white, monochrome typography, cool-gray border/status, one-pixel border, low-elevation shadow, spacing, transition, and `840px` content-width tokens on `#appScreen` only.
    - Replace authenticated-app gradients, glass effects, broad element rules, and persistent-sidebar layout with solid app-scoped surfaces without changing global, landing, or auth selectors.
    - Keep the content column centered and direct-delivery compatible without introducing a build step or production dependency.
    - _Requirements: 1.1, 1.2, 1.4, 1.5, 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 2.8, 2.9, 2.10, 9.11_

  - [x] 1.2 Restructure only `#appScreen` into the top navigation and overlay history drawer
    - Build the `Nova` / `Shopping Assistant` top navigation and move the existing `#newChat`, `#sideToggle`, `#profileControl`, `#profileMenu`, `#userAv`, `#userName`, and `#logout` nodes without changing their identity or auth/profile behavior.
    - Replace the persistent history column with app-local `#historyBackdrop`, labelled `#historyDrawer`, `#historyClose`, and the existing `#hist` container; retain the stream, composer, product panel, and Nova assistant inside the authenticated subtree.
    - Give the recent-conversations opener the exact accessible name `Recent conversations` and synchronized `aria-controls`/`aria-expanded` wiring.
    - _Requirements: 1.1, 1.2, 1.3, 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.13, 9.7, 9.9_

  - [x] 1.3 Implement accessible drawer controls while preserving existing history and session logic
    - Add open/close state synchronization, backdrop and dismiss-button handling, Escape dismissal, focus entry/restoration, Tab trapping, and `inert` enhancement with a fallback.
    - Render recent sessions as native buttons in reverse chronology, mark exactly the active session with `.on` and `aria-current`, and close the drawer after successful session switching or new-chat activation.
    - Continue to use the existing in-memory `sessions`, `sessionId`, `pushHistory`, `saveSession`, and `switchToSession` behavior; do not add storage or alter authentication state.
    - _Requirements: 3.6, 3.7, 3.8, 3.9, 3.10, 3.11, 3.12, 3.13, 7.1, 7.2, 7.7, 7.8, 9.8, 9.9, 9.10_

  - [x] 1.4 Write a property test for history registry cardinality and ordering
    - **Property 1: History exactly represents messaged sessions in reverse chronology**
    - Generate empty and messaged session sequences and verify one entry per messaged session, no empty-session entry, and reverse-chronological ordering.
    - Run at least 100 generated cases in a lightweight development-only DOM harness with the traceability label from the design; add no production dependency.
    - **Validates: Requirements 3.7, 7.1, 7.7**

  - [x] 1.5 Write a property test for session snapshot restoration
    - **Property 2: Session snapshot round trip preserves supported conversation content**
    - Generate sessions containing messages, ReAct details, clarification options, recommendations, and notices; verify equivalent restoration, one active history entry, and operable restored controls.
    - Run at least 100 generated cases in the dependency-free development harness.
    - **Validates: Requirements 3.8, 3.12, 7.2, 7.3**

- [x] 2. Update the exact empty state and composer experience
  - [x] 2.1 Replace the authenticated empty state with the authoritative copy and suggestion controls
    - Preserve `#welcome` for existing session/new-chat restoration while removing authenticated-only decorative orb/effect content and idle animation startup.
    - Use the exact headline `What are you looking for?` and supporting text `Tell me what you need. I’ll help narrow the options and find what fits you best.`
    - Add native suggestion buttons in this exact order: `Running shoes`, `Coffee machine`, `Headphones`, `Camera`; route idle activation through the existing `doSend()` path and prevent activation while busy.
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 2.9_

  - [x] 2.2 Restyle and harden the existing composer without adding unsupported controls
    - Keep the floating composer, textarea autosizing, Enter-to-send, Shift+Enter newline, and existing send pipeline; set the exact placeholder `Tell Nova what you're looking for...`.
    - Style `#send` as a high-contrast black circular `44px` control with an accessible name and directional icon.
    - Centralize disabled-state updates in `syncSendState()` so whitespace-only, busy, success, failure, and reset paths remain consistent and submit at most once.
    - _Requirements: 4.6, 4.7, 4.9, 4.10, 4.11, 4.12, 4.13, 5.12, 9.7, 9.8_

  - [x] 2.3 Write a property test for trigger-independent submission gating
    - **Property 4: Submission is gated and trigger-independent**
    - Generate whitespace, multiline, Unicode, valid, and busy-state inputs for Enter and Send activation; verify exactly one submission iff trimmed input exists and the app is idle.
    - Run at least 100 generated cases without changing the `/chat/stream` request contract.
    - **Validates: Requirements 4.10, 4.11, 4.13**

  - [x] 2.4 Add focused empty-state and composer examples
    - Assert the exact authoritative headline, supporting sentence, placeholder, chip labels/order, chip submission, send disabled state, Enter submission, and Shift+Enter newline behavior.
    - Verify reset and network-failure paths re-enable the composer appropriately.
    - _Requirements: 4.2, 4.3, 4.4, 4.5, 4.7, 4.10, 4.11, 4.12, 4.13, 5.12_

- [x] 3. Restyle messages, loading, clarification, ReAct, and notices without removing behavior
  - [x] 3.1 Apply app-scoped editorial treatments to existing conversation components
    - Restyle shopper messages as right-aligned black bubbles and Nova responses as left-aligned, clearly identified editorial treatments.
    - Restyle loading, ReAct thought/plan/action blocks, clarification options, notices, and errors with solid fills, one-pixel borders, restrained status language, and no continuous decoration.
    - Preserve text safety through existing `textContent`/`esc()` paths and retain all current response content.
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.7, 2.9, 5.1, 5.2, 5.3, 5.5, 5.6, 5.10, 5.11_

  - [x] 3.2 Preserve streamed rendering and make generated controls resilient after session restoration
    - Keep token appending in SSE event order and retain distinct Thought, Plan, and Action labels, inline options, notices, retry-oriented HTTP errors, and connection recovery.
    - Use native clarification buttons plus delegated stream interaction or one rehydration path so restored options remain keyboard-operable.
    - Synchronize selected/disabled/`aria-pressed` state so one clarification group accepts at most one submission while busy.
    - _Requirements: 5.4, 5.5, 5.6, 5.7, 5.8, 5.9, 5.10, 5.11, 5.12, 7.3, 9.8_

  - [x] 3.3 Write a property test for streamed token order
    - **Property 5: Stream tokens preserve event order**
    - Generate finite token sequences including empty strings, whitespace, punctuation, line breaks, and Unicode, then compare rendered text with ordered concatenation.
    - Run at least 100 generated cases.
    - **Validates: Requirements 5.4**

  - [x] 3.4 Write a property test for structured response payload preservation
    - **Property 6: Structured response renderers preserve payload content**
    - Generate ReAct steps, clarification options, and notices; verify each value is safely rendered exactly once, under the correct label, and in source order.
    - Run at least 100 generated cases.
    - **Validates: Requirements 5.5, 5.6, 5.10**

  - [x] 3.5 Write a property test for clarification-group single submission
    - **Property 7: Clarification groups permit at most one submission**
    - Generate non-empty option groups and repeated activation sequences; verify only the first accepted option becomes selected and submits its exact label once.
    - Run at least 100 generated cases.
    - **Validates: Requirements 5.7, 5.8, 5.9**

- [x] 4. Keep recommendations inline and make product browsing explicitly user initiated
  - [x] 4.1 Restyle recommendation cards and remove recommendation-arrival auto-open only
    - Preserve inline card count/order, title, rank, reason, positive summary, negative summary, escaping, recommendation payload handling, and ranking behavior.
    - Make cards native buttons or keyboard-equivalent controls with stable recommendation indices, accessible names, and visible active/focus states.
    - Remove only the `renderRecs()` tail effect that automatically selects the first card and opens the product panel; recommendation arrival must not set active-card, panel, tab, or iframe state.
    - _Requirements: 1.3, 5.10, 6.1, 6.2, 6.3, 9.8_

  - [x] 4.2 Wire explicit card activation to existing product-panel selection behavior
    - On explicit activation, clear sibling state, mark the clicked card active, open the existing browser panel, select that exact index, synchronize ARIA, and focus the panel close control.
    - Preserve product tabs, embedded browsing, external links, iframe cleanup, panel close behavior, and the existing desktop width clamp; clear card state and restore focus when closing.
    - Add separator semantics and keyboard-safe resizing without changing the existing minimum/maximum limits; make later card activations update the open panel.
    - _Requirements: 6.4, 6.5, 6.6, 6.7, 6.8, 6.9, 9.7, 9.8, 9.9, 9.10_

  - [x] 4.3 Write a property test for inline non-interrupting recommendation arrival
    - **Property 8: Recommendation arrival is inline and non-interrupting**
    - Generate valid recommendation arrays and verify one complete card per item in source order while a closed product panel stays closed and every card stays inactive.
    - Run at least 100 generated cases, including empty and multi-card payloads.
    - **Validates: Requirements 6.1, 6.2, 6.3**

  - [x] 4.4 Write a property test for explicit recommendation selection lifecycle
    - **Property 9: Recommendation selection follows the last explicit activation**
    - Generate valid card-index sequences and verify each activation selects the same card/product, the final index wins, and closing hides the panel and clears active state.
    - Run at least 100 generated cases, emphasizing non-first selections and repeated changes.
    - **Validates: Requirements 6.4, 6.5, 6.6, 6.9**

  - [x] 4.5 Write a property test for product-panel resize clamping
    - **Property 10: Product-panel resizing is clamped**
    - Generate desktop viewport and pointer widths around both boundaries and compare panel width with the existing clamp formula.
    - Run at least 100 generated cases where the clamp interval is valid.
    - **Validates: Requirements 6.8**

- [x] 5. Complete session, new-chat, and panel-state integration
  - [x] 5.1 Implement the app-local state model and session lifecycle interfaces across components
    - Preserve the existing `sessions: Record<string, {title, html}>` and `sessionId` data model, first-message history creation, fresh runtime IDs, empty-session exclusion, memory-only reload behavior, and snapshots containing messages, ReAct details, clarification options, recommendations, and notices.
    - Keep drawer, profile, Nova quick-panel, and product-panel state represented by the designed app classes/hidden and ARIA states, with `busy`, `activeRecCard`, `historyOpener`, and `productPanelOpener` synchronized through the app-local controller functions rather than a new store or API.
    - Implement the designed `saveSession`, `pushHistory`, and `switchToSession` transitions atomically: reject unknown IDs without mutation, save current content, restore the target, re-establish exactly one active history entry, close product/history surfaces through their controller interfaces, and retain restored control operability through stream delegation or one rehydration path.
    - Make New Chat create a fresh ID, restore `#welcome`, clear history/product selection, close overlays using the existing `closeHistoryDrawer`, `closeProduct`, and quick-panel behavior, reset metadata, call `syncSendState()`, and focus the composer without creating an empty history entry.
    - _Requirements: 3.8, 3.9, 3.12, 6.10, 7.1, 7.2, 7.3, 7.4, 7.5, 7.6, 7.7, 7.8, 9.10_

  - [x] 5.2 Write a property test for product-panel closure on session changes
    - **Property 3: Session changes close product browsing**
    - Generate source/target sessions with active recommendations and verify switching or creating a chat closes the browser, clears active-card state, and leaves the target snapshot unchanged.
    - Run at least 100 generated cases.
    - **Validates: Requirements 6.10, 7.6**

  - [x] 5.3 Write a property test for new-chat identifier uniqueness
    - **Property 11: New-chat identifiers are unique within the active runtime**
    - Generate finite New Chat activation sequences and verify each live identifier is unique and each fresh empty chat remains absent from history until its first valid message.
    - Run at least 100 generated cases.
    - **Validates: Requirements 7.4, 7.7**

- [x] 6. Subdue the Floating Nova Assistant and coordinate overlay accessibility
  - [x] 6.1 Restyle the existing Nova assistant as a subordinate app-scoped control
    - Retain `#novaBuddy`, `#nbPanel`, existing quick-start actions, and `#nbNewChat`, but use a restrained monochrome treatment no more visually prominent than the composer/conversation.
    - Remove continuous bob, glow, pulse, orbit, bounce, arm, blink, and idle movement while keeping at least a `44px` hit target.
    - _Requirements: 2.8, 2.9, 8.1, 8.2, 8.3, 8.4, 9.7_

  - [x] 6.2 Add native, keyboard-safe quick-panel and overlay coordination behavior
    - Synchronize `aria-controls`, `aria-expanded`, and `aria-hidden`; focus the first quick action on open and restore focus on Escape, outside activation, or close.
    - Route quick-start text through `doSend()` and delegate new conversation to `#newChat.click()` while honoring busy state.
    - Ensure opening history, profile, Nova quick actions, or product browsing closes conflicting lightweight surfaces and Escape dismisses only the topmost surface.
    - _Requirements: 3.13, 8.5, 8.6, 8.7, 9.8, 9.9, 9.10_

  - [x] 6.3 Add focused assistant and overlay interaction tests
    - Verify native keyboard activation, busy-state quick-action gating, New Chat delegation, single-overlay coordination, ARIA synchronization, Escape ordering, and focus restoration.
    - _Requirements: 8.5, 8.6, 8.7, 9.8, 9.9, 9.10, 10.11_

- [x] 7. Add responsive and reduced-motion behavior scoped to `#appScreen`
  - [x] 7.1 Implement the desktop, tablet, and mobile app layouts
    - Keep the `840px` content/composer column centered at desktop, use an overlay history drawer, and retain the resizable product column within existing desktop limits.
    - At tablet width, keep every top-navigation action reachable without horizontal page scrolling and overlay both history/product surfaces.
    - At mobile width, constrain all app content to the viewport, collapse recommendation summaries, keep drawer/panel close controls reachable, use dynamic viewport/safe-area sizing, and offset the assistant above the composer.
    - _Requirements: 2.6, 2.10, 6.8, 9.1, 9.2, 9.3, 9.5, 9.6, 9.7_

  - [x] 7.2 Implement keyboard-viewport recovery and reduced-motion overrides
    - Use `visualViewport` when available to keep the latest message and composer reachable during mobile on-screen-keyboard resizing, with existing window/scroll fallbacks when unavailable.
    - Scope reduced-motion rules to authenticated app animation/scrolling, remove decorative transforms and continuous animation, and keep ordinary transitions within `120–240ms` otherwise.
    - _Requirements: 2.9, 4.6, 9.4, 9.11, 9.12_

  - [x] 7.3 Add automated responsive and motion regression checks
    - Verify `1440x900`, `834x1112`, and `390x844` viewports for centered/full-width content, reachable navigation, fitting overlays, visible close controls, no horizontal document scroll, and latest-message/composer reachability.
    - Emulate focused-input visual-viewport resizing and reduced motion; assert app state changes remain usable without decorative translation or continuous animation.
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5, 9.6, 9.11, 9.12, 10.10_

- [x] 8. Add focused validation and protected-surface regression coverage
  - [x] 8.1 Add dependency-free static, syntax, host, and change-boundary checks
    - Parse `static/index.html` for valid/balanced structure, extract embedded JavaScript and run a syntax check, and compile `main.py` plus `app/**/*.py` without modifying Python files.
    - Add a diff/selector guard that permits production changes only in authenticated `#appScreen` CSS/DOM/chat JavaScript and rejects changes to landing/login/register presentation, auth logic/storage, APIs, routes, Python business logic, agents/prompts, and recommendation output behavior.
    - Inspect `renderRecs()` to reject recommendation-arrival calls that open/select product browsing outside explicit card activation.
    - Use existing or temporary development tooling only; do not add a production dependency or frontend build step.
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.8, 1.9, 6.2, 6.3, 10.1, 10.2, 10.12, 10.13_

  - [x] 8.2 Add an authenticated browser/runtime and SSE regression scenario
    - Exercise the unchanged authentication entry into `#appScreen` and fail on uncaught browser exceptions or console errors.
    - Mock or fixture the existing `/chat/stream` contract to verify one send, correct request shape, loading, ordered token receive/rendering, successful cleanup, HTTP retry messaging, and connection-error composer recovery.
    - _Requirements: 1.3, 5.3, 5.4, 5.11, 5.12, 10.3, 10.4_

  - [x] 8.3 Add clarification and recommendation browser regression scenarios
    - Verify suggestion and clarification submissions use the existing send path, selected clarification styling is exclusive, and repeated option activation is blocked.
    - Verify recommendation arrival stays inline without auto-open, explicit activation of a non-first card opens/selects that product, later activation updates selection, and close clears selection/restores focus.
    - Preserve and check embedded browsing/external-link behavior without changing recommendation data or ranking.
    - _Requirements: 4.5, 5.6, 5.7, 5.8, 5.9, 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7, 6.9, 10.5, 10.6, 10.7_

  - [x] 8.4 Add history, session-switching, and product-panel regression scenarios
    - Verify first-message history population, reverse chronology, no empty-chat entry, New Chat reset, drawer open/dismiss/Escape behavior, session switching, and restoration of messages plus all structured descendants.
    - Verify session changes close product browsing and verify desktop pointer/keyboard resizing and close behavior remain within existing limits.
    - _Requirements: 3.7, 3.8, 3.9, 3.10, 3.11, 3.12, 6.8, 6.9, 6.10, 7.1, 7.2, 7.3, 7.4, 7.5, 7.6, 7.7, 10.8, 10.9_

  - [x] 8.5 Add keyboard, focus, ARIA, and target-size regression scenarios
    - Exercise keyboard-only operation of the composer, all top-navigation actions, history drawer, profile control/menu, clarification options, recommendation cards, product close/resize controls, and Floating Nova Assistant.
    - Assert visible focus, minimum primary icon target size, dialog/panel identification, synchronized expanded/hidden/current/pressed states, focus trapping where applicable, and opener focus restoration.
    - _Requirements: 3.4, 3.11, 3.13, 4.11, 4.12, 5.7, 6.4, 6.8, 6.9, 8.5, 8.6, 8.7, 9.7, 9.8, 9.9, 9.10, 10.11_

  - [x] 8.6 Add protected landing/auth visual and behavior regression checks
    - Compare landing, login, and registration presentation before/after at representative desktop and mobile sizes and fail on any protected-surface visual difference.
    - Run existing auth and project tests and inspect the final diff for changes to auth storage/requests, route contracts, backend Python, Agent code/prompts, or recommendation output/ranking.
    - _Requirements: 1.2, 1.3, 10.12, 10.13_

- [x] 9. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Specification creation modifies only files within `.kiro/specs/nova-chat-interface-redesign/`; it does not modify application source or test files.
- During later implementation task execution, production application changes are limited to authenticated-chat CSS, the `#appScreen` subtree, and chat/session/product/Nova-assistant JavaScript in `static/index.html`.
- Development and test artifacts required by the validation suite are permitted only during later implementation task execution.
- The exact empty-state headline, supporting copy, and composer placeholder in this plan match `Approved_Chat_Copy` in `requirements.md`.
- Tasks marked with `*` are optional test tasks for faster implementation, but together they provide the requested acceptance and regression evidence.
- Property tasks map one-to-one to the 11 correctness properties and should use at least 100 generated cases without adding production dependencies.
- No task changes landing/login/register presentation, auth logic or storage, backend APIs/routes, Python business logic, Agent code/prompts, or recommendation behavior.

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1"] },
    { "id": 1, "tasks": ["1.2"] },
    { "id": 2, "tasks": ["1.3"] },
    { "id": 3, "tasks": ["1.4", "1.5"] },
    { "id": 4, "tasks": ["2.1"] },
    { "id": 5, "tasks": ["2.2"] },
    { "id": 6, "tasks": ["2.3", "2.4"] },
    { "id": 7, "tasks": ["3.1"] },
    { "id": 8, "tasks": ["3.2"] },
    { "id": 9, "tasks": ["3.3", "3.4", "3.5"] },
    { "id": 10, "tasks": ["4.1"] },
    { "id": 11, "tasks": ["4.2"] },
    { "id": 12, "tasks": ["4.3", "4.4", "4.5"] },
    { "id": 13, "tasks": ["5.1"] },
    { "id": 14, "tasks": ["5.2", "5.3"] },
    { "id": 15, "tasks": ["6.1"] },
    { "id": 16, "tasks": ["6.2"] },
    { "id": 17, "tasks": ["6.3"] },
    { "id": 18, "tasks": ["7.1"] },
    { "id": 19, "tasks": ["7.2"] },
    { "id": 20, "tasks": ["7.3", "8.1", "8.2"] },
    { "id": 21, "tasks": ["8.3", "8.4", "8.5", "8.6"] }
  ]
}
```
