# DS-007 — UI/UX Bible

## Document Control

| Field | Value |
|---|---|
| Document ID | DS-007 |
| Title | UI/UX Bible |
| Version | 0.2.1 |
| Status | Draft |
| Owner | TheSinnerMan |
| Contributors | |
| Classification | Internal |
| Repository | LightSwornPVP/DarkSage |
| Created | 2026-07-24 |
| Last Updated | 2026-07-24 |

Status lifecycle: Draft → Under Review → Approved → Superseded/Deprecated.

## Revision History

| Version | Date | Author | Summary |
|---|---|---|---|
| 0.1.0 | 2026-07-24 | TheSinnerMan | First controlled draft, authored as part of the Batch 1 grouped pass (DS-007/DS-008/DS-009). Translates DS-001's Presentation Independence, Explainability Standard, and Product Experience Principles, together with DS-002's DS-WKS/DS-USR/DS-NFR families and DS-006's UI-relevant API contracts, into detailed interface behavior requirements under the `DS-UX` prefix. |
| 0.2.0 | 2026-07-24 | TheSinnerMan | Targeted repair for independent-audit finding DS-007-H1: added `DS-UX-016` (Interface State Lifecycle, Committed/MVP) defining the Loading → Ready → Refreshing → Degraded/Partial → Error → Retry/Recovery transition model, integrating rather than duplicating DS-UX-012 (data-state labeling) and DS-UX-015 (error presentation), and adding an accessibility state-announcement acceptance criterion. Inserted before the prior DS-UX-016 through DS-UX-020, which were renumbered DS-UX-017 through DS-UX-021 respectively (all internal cross-references updated) to keep requirement IDs in document order. |
| 0.2.1 | 2026-07-24 | TheSinnerMan | Narrow repair for independent-audit finding DS-007-H1 (accessibility classification): removed `DS-UX-016`'s assistive-technology announcement acceptance criterion and testing clause, since it depended on the Planned `DS-NFR-004`/`DS-UX-017` accessibility work while `DS-UX-016` itself is Committed/MVP. Added `DS-UX-022` (Accessible Interface State Announcements, Planned), tracing to `DS-NFR-004`/`DS-UX-017`, owning assistive-technology announcements and non-visual state/staleness disclosure for the `DS-UX-016` lifecycle. `DS-UX-016`'s Committed/MVP core (loading, ready, refreshing, degraded/partial, stale-data disclosure, error, retry/recovery, safe data preservation, visible incomplete/delayed/unavailable disclosure) is unchanged and unweakened. |

## 1. Purpose

DS-007 is the authoritative specification of DarkSage's UI/UX behavior: how Workspace Studio behaves, how Presentation Independence is enforced at the interface layer, how terminology modes work, how explainability and risk are surfaced, how charts and data state are presented, and the product's accessibility and desktop-first interaction commitments. Where DS-002's DS-WKS/DS-USR/DS-NFR families state *what* the product must do at the requirements level, DS-007 states *how that obligation is discharged* in interface-behavior terms — without prescribing a specific component library, visual design system, or pixel-level layout.

## 2. Scope

This document governs:

- Presentation Independence enforcement at the UI layer (ADR-004);
- Workspace Studio behavior (layout, drag-and-drop, saved/purpose-specific workspaces, density, multi-monitor direction);
- terminology mode presentation (professional / Codex-themed);
- explainability-first presentation of material conclusions;
- risk visibility and data-state/provenance presentation;
- chart and technical-analysis presentation, including cross-engine consistency;
- accessibility conformance;
- desktop-first interaction patterns; and
- error, empty, and degraded-state presentation.

DS-007 does not govern: product-level feature commitments (DS-002), technical implementation architecture (DS-004), database design (DS-005), API contracts (DS-006 — authoritative for all callable client/backend behavior; DS-007 describes how the UI *presents* what DS-006 exposes, never a different contract), Sage's internal reasoning/evidence governance (DS-003), security architecture (DS-008), or testing procedure (DS-009). DS-007 does not define visual branding, color palette, or typography — those belong to `docs/standards/BRAND_GUIDE.md` and `docs/standards/STYLE_GUIDE.md`.

## 3. Audience

Frontend/desktop contributors, UX designers, independent auditors, and future Codex authors implementing or extending DarkSage's interface.

## 4. Definitions

See DS-001 §24 and DS-002 §4. Additional terms:

| Term | Meaning |
|---|---|
| Capability state | Whether an underlying system capability (data source, calculation, evidence access) is enabled — independent of whether any UI surface currently displays it (DS-PRD-003) |
| Presentation state | What is currently visible/arranged in a workspace — never itself a source of capability |
| Progressive disclosure | Presenting advanced detail through secondary panels, expandable sections, or explicit "advanced" affordances rather than surfacing everything at once or removing it from the product |

## 5. UI Design Principles

### DS-UX-001 — Presentation Independence Enforcement

**Release Classification:** Committed / MVP | **Governing Source:** DS-PRD-003 (Committed); ADR-004; DS-001 §16

**Description:** The UI shall maintain capability state and presentation state as separate models. Hiding, moving, removing, or rearranging a widget shall never disable, gate, or otherwise depend on for its continued existence any underlying enabled capability, data source, or Sage evidence access. A capability is never toggled as a side effect of a layout edit; capability changes require their own explicit, distinguishable action (e.g., a Settings/Integrations surface), never a workspace-editing gesture. Widget visibility is presentation only — it is never itself an enabled-system-capability control, and no future UI pattern may repurpose widget visibility into a capability gate without a new ADR.

**Acceptance Criteria:**
- Removing every widget referencing a given data source or calculation from every workspace does not disable that data source or calculation; it remains available to Sage and to any widget re-added later.
- No client code path uses "is widget X visible" as an input to a capability-gating decision.
- Restoring a previously hidden widget never requires a separate re-enable action.

**Testing:** Regression test: hide/remove each Committed/MVP widget in turn and confirm no change in evidence availability or calculation results (shared with DS-PRD-003's own test).

### DS-UX-002 — Workspace Studio Baseline Layout

**Release Classification:** Committed / MVP | **Governing Source:** DS-WKS-001 (Committed); `ROADMAP.md` Phase 1

**Description:** The UI shall let a user add, remove, resize, and arrange workspace widgets within the active workspace, backed by `GET /workspace/layout/current` / `PUT /workspace/layout/current` (DS-API-WKS-001, DS-006 — Committed/MVP, ephemeral session-scoped state, no dependency on persisted layout storage). Removing all widgets leaves an explicit "add widget" affordance reachable rather than an empty, dead-ended view. A widget that depends on a currently-disabled capability (e.g., an unconfigured integration) is shown clearly as unavailable, not silently omitted or silently broken.

**Acceptance Criteria:**
- Add/remove/resize/arrange operations for every Committed/MVP widget round-trip correctly through DS-API-WKS-001 within a single session.
- The UI never presents durable cross-session persistence as available for this baseline layout — that capability belongs exclusively to DS-UX-004 (Planned), matching DS-API-WKS-001's own scope boundary (DS-006 §6.5, H2 repair).
- A widget resized below a usable minimum is prevented or gracefully clamped, never rendered unusable or invisible.

**Testing:** Add/remove/resize regression test per Committed/MVP widget type (shared with DS-WKS-001's own test).

### DS-UX-003 — Drag-and-Drop Layout

**Release Classification:** Planned | **Governing Source:** DS-WKS-002 (Planned)

**Description:** The UI should support drag-and-drop repositioning and resizing of workspace widgets, with a documented, deterministic collision rule (swap, push, or reject) and a cancellable in-progress drag (e.g., Escape or invalid drop target).

**Acceptance Criteria:** Matches DS-WKS-002's acceptance criteria exactly; a keyboard-only equivalent is available per DS-UX-017.

**Testing:** Drag-and-drop interaction test including cancel path and collision handling (shared with DS-WKS-002's own test).

### DS-UX-004 — Saved and Purpose-Specific Workspaces

**Release Classification:** Planned | **Governing Source:** DS-WKS-003, DS-WKS-004 (both Planned); DS-API-WKS-002 (DS-006, Planned)

**Description:** The UI should let a user save, name, switch between, and organize multiple workspaces (including purpose-specific presets), backed by DS-API-WKS-002's persisted-layout CRUD and activation contract. Once implemented, activating a saved workspace becomes the mechanism that populates DS-UX-002's active composition — the UI never introduces a second, parallel persistence path outside DS-API-WKS-002.

**Acceptance Criteria:**
- Switching workspaces does not lose unsaved state in a workspace not currently active, consistent with DS-WKS-004.
- A layout referencing a widget type that no longer exists degrades gracefully on load, not a load failure (DS-WKS-003's edge case).

**Testing:** Multi-workspace switch regression test; degraded-widget-load test (shared with DS-WKS-003/004's own tests).

### DS-UX-005 — Information Density Control

**Release Classification:** Planned | **Governing Source:** DS-WKS-005 (Planned)

**Description:** The UI should let a user adjust workspace information density (compact/comfortable, or an equivalent scale) without affecting underlying capability, per DS-PRD-003.

**Acceptance Criteria:** Density changes are presentation-only, per DS-UX-001.

**Testing:** Density-switch regression test confirming no functional change.

### DS-UX-006 — Multi-Monitor and Detachable Workspaces

**Release Classification:** Future / Exploratory | **Governing Source:** DS-WKS-006 (Future/Exploratory); DS-001 §19.1

**Description:** The UI may, in a future release, support workspace layouts spanning multiple monitors or detached workspace windows. This capability is not committed to current or near-term Planned scope; no UI pattern authored under this document may assume its existence.

**Acceptance Criteria:** N/A at Future/Exploratory classification, matching DS-WKS-006.

**Testing:** Not applicable until promoted.

### DS-UX-007 — Terminology Mode Presentation

**Release Classification:** Planned | **Governing Source:** DS-USR-003 (Planned); DS-001 §17

**Description:** The UI shall provide a user-selectable terminology mode (professional / Codex-themed) governing display labels only, per the mapping table in DS-001 §17 / `docs/standards/STYLE_GUIDE.md` (this document does not redefine that mapping). Switching modes changes only labels and in-product copy — never enabled capability, data, or calculation results. A themed label is never the *only* label for a professional financial concept without an accessible plain-language equivalent (tooltip or settings mapping). Sage's conversational output (once built, Planned Phase 6) respects the active mode for consistency, per DS-USR-003's own edge case.

**Acceptance Criteria:** Matches DS-USR-003's acceptance criteria; mode-switch regression test covers every themed label in the current Committed/MVP surface.

**Testing:** Mode-switch regression test verifying no functional change accompanies the label change (shared with DS-USR-003's own test).

### DS-UX-008 — Persona-Informed Defaults and Progressive Disclosure

**Release Classification:** Planned | **Governing Source:** DS-USR-004, DS-USR-005 (both Planned); DS-001 §18, §19

**Description:** The UI should offer capability-based persona presets that adjust only default presentation (initial layout density, suggested terminology mode) and should present advanced configuration/analytical depth through progressive disclosure rather than by removing it from the product. No capability is gated behind a persona selection, and every Committed/MVP capability remains reachable by an advanced user without a workspace rebuild.

**Acceptance Criteria:** Matches DS-USR-004/005's acceptance criteria exactly.

**Testing:** Preset-selection test confirming identical capability surface across personas; usability walkthrough confirming default-view/advanced-view balance (shared with DS-USR-004/005's own tests).

## 6. Explainability and Risk Presentation

### DS-UX-009 — Explainability-First Conclusion Presentation

**Release Classification:** Committed / MVP for the Signal why-trade/why-not-trade surface; Planned for the Sage conversational extension | **Governing Source:** DS-001 §15 (Explainability Standard); DS-SIG-003 (Committed); DS-PRD-002, DS-PRD-009 (both Committed); DS-AI-003/DS-SGE (Planned, Phase 6)

**Description:** Every material conclusion surface shall present, through a consistent expandable pattern, the answers DS-001 §15 requires where applicable: why the conclusion was reached, supporting evidence and its currency, uncertainty, material risk, key assumptions, and what would invalidate it. For the current Committed/MVP surface, this is the Signal detail / why-trade / why-not-trade view, backed by `GET /signals/{signal_id}/reasons` (DS-API-SIG-002, DS-006) and DS-SIG-003's defined reason vocabulary. The Sage-specific conversational instantiation of this same pattern (backed by `GET /sage/messages/{id}/evidence`, DS-API-AI-002) is Planned, Phase 6, and reuses this document's expandable-explanation pattern rather than introducing a second one once built.

**Acceptance Criteria:**
- The Signal detail surface exposes DS-SIG-003's full reason set without requiring the user to leave the surface or issue a separate query.
- An explanation never presents polished language in place of disclosing a limitation or conflict, per DS-001 §15.
- Where evidence is insufficient, the surface communicates uncertainty or abstention rather than a fabricated-looking answer (DS-PRD-009).

**Testing:** Content-completeness audit against DS-SIG-003's reason vocabulary for the Signal detail surface (shared with DS-SIG-003's own test).

### DS-UX-010 — Uncertainty and Confidence Labeling

**Release Classification:** Committed / MVP | **Governing Source:** DS-PRD-009 (Committed)

**Description:** Any forward-looking, probability-based, or model-generated statement rendered in the UI shall carry a visible label distinguishing it from an observed historical fact, using a consistent, defined vocabulary/scale reused across every surface rather than ad hoc per-feature wording. A high-confidence output is still labeled as a model output — confidence level never upgrades a forecast's visual treatment to that of a fact.

**Acceptance Criteria:** Matches DS-PRD-009's acceptance criteria; the shared vocabulary is defined once (DS-003/DS-SGE-014 once Sage exists) and reused, never redefined per widget.

**Testing:** Content-review test across every forecast/score-producing surface confirming a label is present and no guarantee language appears (shared with DS-PRD-009's own test).

### DS-UX-011 — Material Risk Visibility

**Release Classification:** Committed / MVP baseline; Planned for the configured-limit warning surface | **Governing Source:** DS-001 §8.4, §13; DS-PRD-006 (Committed); DS-RSK-003 (Planned)

**Description:** Any Committed/MVP surface presenting a risk-relevant figure (Signal detail, Scanner result) displays it without requiring extra navigation or an expand action to first discover that risk information exists (though detail may be progressively disclosed per DS-UX-008). Risk information is never omitted or visually de-emphasized to make an opportunity appear more attractive. Once configured risk limits/warnings exist (DS-RSK-003, Planned), a limit breach is surfaced at the point of the relevant decision — never buried in a separate report only — and is never suppressed by workspace layout, per DS-UX-001/DS-PRD-003.

**Acceptance Criteria:**
- No Committed/MVP surface requires a user action solely to reveal that material risk information exists (its full detail may still require an action to expand).
- Once DS-RSK-003 exists, a limit breach in any workspace configuration produces a visible warning within the same defined latency window (DS-NFR-002) regardless of which widgets are currently arranged.

**Testing:** Content-audit test confirming risk visibility on Committed/MVP surfaces; limit-breach visibility test across varied workspace configurations once DS-RSK-003 exists (shared with DS-RSK-003's own test).

### DS-UX-012 — Data State and Provenance Indicators

**Release Classification:** Committed / MVP | **Governing Source:** DS-PRD-008 (Committed); DS-API-COR-002 (DS-006, Committed)

**Description:** Every material data value rendered in the UI shall carry a discoverable state indicator (current / delayed / stale / historical / simulated) and, where applicable, a timestamp, sourced from DS-API-COR-002's response envelope — the UI never derives or guesses a state label independently of what the API returns. In a mixed-state view (some symbols current, some delayed), each item is labeled individually; one blanket label is never applied to an entire view. Backtest/simulated output is visually and textually distinguishable from live data in every surface it appears, per DS-PRD-008/DS-BKT-004.

**Acceptance Criteria:** Matches DS-PRD-008's acceptance criteria exactly; a feed interruption surfaces the stale/delayed indicator within DS-MKT-004's defined threshold window (10s real-time / delay+60s delayed / 1hr post-close EOD).

**Testing:** Feed-interruption simulation test verifying indicators appear within the defined threshold window (shared with DS-PRD-008/DS-MKT-004's own tests).

## 7. Chart Presentation

### DS-UX-013 — Chart Presentation and Cross-Engine Consistency

**Release Classification:** Committed / MVP | **Governing Source:** DS-CHT-001, DS-CHT-002 (both Committed); DS-ARC-008 (Committed); DS-API-CHT-001 (DS-006, Committed)

**Description:** The UI shall present price charts and technical indicators using the dual chart engines DS-ARC-008 establishes (Apache ECharts, TradingView Lightweight Charts), consuming the single response DS-API-CHT-001 returns. Indicator values are visually identical regardless of which engine renders them — the UI is a rendering choice, never a second source of indicator computation (DS-ARC-007). Insufficient historical data for an indicator's lookback period is disclosed as such, not silently rendered as a misleading partial value.

**Acceptance Criteria:** Matches DS-ARC-008/DS-CHT-002's acceptance criteria; a cross-renderer parity test confirms pixel-independent value identity between engines.

**Testing:** Cross-renderer data-parity test (shared with DS-ARC-008's own test).

### DS-UX-014 — Chart Annotations Presentation

**Release Classification:** Planned | **Governing Source:** DS-CHT-003 (Planned); DS-API-CHT-002 (DS-006, Planned)

**Description:** The UI should let a user create, view, and delete chart annotations, backed by DS-API-CHT-002's CRUD contract.

**Acceptance Criteria:** Matches DS-CHT-003's acceptance criteria.

**Testing:** Deferred to DS-CHT-003's own implementation timing.

## 8. Error, Empty, and Degraded States

### DS-UX-015 — Understandable Error and Empty States

**Release Classification:** Committed / MVP | **Governing Source:** DS-OPS-003 (Committed); DS-API-COR-006 (DS-006, Committed)

**Description:** The UI shall present errors in plain language describing what happened and, where applicable, what the user can do next, sourced from DS-API-COR-006's structured error schema — raw technical detail (stack trace, error code) is available on request/expansion, never as the primary message. No Committed/MVP user-initiated action fails silently (with no visible indication). A transient error (e.g., a network blip) is visually distinguished from a persistent error requiring user action. An empty state (no data, no results) presents a clear next action rather than a blank or ambiguous surface.

**Acceptance Criteria:** Matches DS-OPS-003's acceptance criteria exactly.

**Testing:** Error-message content audit across a fixture set of Committed/MVP failure scenarios (shared with DS-OPS-003's own test).

### DS-UX-016 — Interface State Lifecycle

**Release Classification:** Committed / MVP | **Governing Source:** DS-PRD-008, DS-PRD-010 (both Committed); DS-UX-012, DS-UX-015 (this document); DS-API-COR-002 (DS-006, Committed)

**Description:** Every data-bearing surface shall progress through a coherent, testable interface-state lifecycle: **Loading** (initial fetch, no prior data available) → **Ready** (current, complete data displayed) → **Refreshing** (a background/foreground update in progress while previously valid data remains visible where safe) → **Degraded / Partial** (some but not all expected data is available, or the data source itself is degraded) → **Error** (the surface cannot produce a usable result) → **Retry / Recovery** (a user- or system-initiated retry, returning to Loading or Refreshing). This requirement defines the *transitions and integrity guarantees* between these states; it does not redefine DS-UX-012's data-state/provenance labeling (current/delayed/stale/historical/simulated — this lifecycle's Ready and Degraded states display that labeling per DS-UX-012, not a new one) or DS-UX-015's error-content presentation (this lifecycle's Error state uses DS-UX-015's plain-language/expandable-detail pattern verbatim) — DS-UX-016 integrates both rather than duplicating them.

State transition rules:
- **Loading → Ready**: on successful initial fetch with complete data.
- **Loading → Error**: on initial-fetch failure with no prior data to fall back to.
- **Ready → Refreshing**: on a background or user-initiated refresh; previously valid data remains visible and interactive during the refresh wherever it is still safe to act on.
- **Refreshing → Ready**: on successful refresh returning complete, current data.
- **Refreshing → Degraded / Partial**: when a refresh returns incomplete data or a data source becomes degraded mid-refresh; previously valid data for the unaffected portion remains visible, and the affected portion is clearly marked incomplete, stale, delayed, or unavailable (DS-UX-012).
- **Degraded / Partial → Ready**: on a subsequent successful refresh restoring complete, current data.
- **Any state → Error**: on an unrecoverable failure (e.g., the data source is unreachable and no usable prior data exists), presented per DS-UX-015.
- **Error → Retry / Recovery**: on a user- or system-initiated retry attempt.
- **Retry / Recovery → Loading** (no prior data survives) **or → Refreshing** (prior data survives): a retry never jumps directly to Ready without passing through a fetch attempt.

**Acceptance Criteria:**
- No surface presents Loading, Refreshing, Degraded/Partial, or Error-state data with the same visual/textual treatment as Ready-state (current, complete) data — DS-UX-012's state indicator is present in every non-Ready state, not only Error.
- Previously valid data is preserved and remains visible during Refreshing wherever continuing to display it would not itself mislead the user about currency; where displayed, it carries its actual, non-current state label (DS-UX-012) rather than being silently upgraded to look current.
- A Degraded/Partial state explicitly discloses which portion of the expected data is incomplete, stale, delayed, or unavailable — never a blanket "something is wrong" with no further detail.
- Retry is available from Error and Degraded/Partial states, and a retry attempt is visibly distinguishable from a fresh Loading state where prior data exists.
- No lifecycle state or transition depends on which widgets are currently visible in a workspace (Presentation Independence, DS-UX-001) — the same underlying capability's lifecycle state is consistent regardless of how many surfaces currently render it.

Non-visual (assistive-technology) announcement of these state transitions is a separate, Planned obligation — see DS-UX-022 — and is not a Committed/MVP acceptance criterion of this requirement, since it depends on accessibility conformance work (DS-NFR-004/DS-UX-017) that is itself Planned. This requirement's Committed/MVP lifecycle (visual/textual presentation, data preservation, and disclosure) is complete and fully testable independent of DS-UX-022's implementation status.

**Testing:** State-transition regression test exercising every listed transition, including the data-preserved-during-Refreshing and partial-disclosure-during-Degraded cases. Assistive-technology state-announcement testing belongs to DS-UX-022 (Planned), not this requirement.

## 9. Accessibility and Interaction Patterns

### DS-UX-017 — Accessibility Conformance

**Release Classification:** Planned | **Governing Source:** DS-NFR-004 (Planned)

**Description:** The UI should conform to a documented accessibility standard (e.g., WCAG 2.2 Level AA) for applicable desktop UI patterns and should support keyboard-only operation of every Committed/MVP workflow, including workspace layout editing (DS-UX-002/DS-UX-003). Text contrast and status indication do not rely on color alone; a chart or visualization conveying status by color also conveys it via text/label.

**Acceptance Criteria:** Matches DS-NFR-004's acceptance criteria exactly.

**Testing:** Keyboard-only workflow completion test; automated accessibility-conformance scan against the documented standard (shared with DS-NFR-004's own test).

### DS-UX-018 — Desktop-First Interaction Patterns

**Release Classification:** Committed / MVP | **Governing Source:** ADR-001 (Desktop-First); DS-ARC-002 (Committed); DS-001 §20

**Description:** The primary interaction model targets mouse-and-keyboard desktop conventions (native menus, keyboard shortcuts, resizable/multi-pane windows) appropriate to the Electron shell DS-ARC-002 establishes, rather than a touch-first or mobile-first interaction model. Desktop-first does not prohibit a future mobile-appropriate interaction model (DS-UX-020) — it establishes which model governs the current primary surface.

**Acceptance Criteria:**
- Every Committed/MVP workflow is fully operable via mouse and keyboard without requiring touch input.
- No Committed/MVP interaction pattern assumes a touch-only input method.

**Testing:** Desktop-launch smoke test (shared with DS-ARC-002's own Phase 1 exit criterion); keyboard/mouse operability walkthrough.

### DS-UX-019 — Progressive Disclosure of Advanced Capability

**Release Classification:** Planned | **Governing Source:** DS-USR-005 (Planned); DS-001 §18, §19

**Description:** See DS-UX-008 (Persona-Informed Defaults and Progressive Disclosure), which states this obligation in full; this entry cross-references it to keep the interaction-pattern section complete without duplicating the requirement text.

**Testing:** See DS-UX-008.

## 10. Cross-Platform and Future Extensibility

### DS-UX-020 — Mobile Presentation Parity Boundary

**Release Classification:** Planned | **Governing Source:** DS-ARC-003 (Planned, Phase 9); DS-001 §20

**Description:** Once a mobile client exists (Phase 9), its UI shall present the same backend-authoritative state desktop observes at the same point in time (DS-ARC-003's cross-client consistency requirement) and shall never introduce a locally-computed alternative presentation of trading/Auto-Trader state. Mobile's interaction model (touch-first) differs from desktop's (DS-UX-018), but Presentation Independence (DS-UX-001) and every other principle in this document apply identically across platforms — no client, presentation surface, or platform may silently gain execution authority merely by existing on a different platform (DS-001 §20).

**Acceptance Criteria:** Matches DS-ARC-003's acceptance criteria exactly.

**Testing:** Cross-client state-consistency test (shared with DS-ARC-003's own test, Phase 9).

### DS-UX-021 — Sage Conversational UI Boundary

**Release Classification:** Planned, Phase 6 | **Governing Source:** DS-PRD-005 (Committed, the underlying boundary); DS-AI-001, DS-SGE-005 (Planned)

**Description:** Once the Sage conversational surface exists (backed by `POST /sage/messages`, DS-API-AI-001), the UI shall visually and textually distinguish Sage's recommendation language from confirmed-action language — the presence of a Sage response is never, by itself, rendered in a way that could be mistaken for an executed action. Any action Sage recommends still requires its own separate, explicit confirmation step through the relevant domain surface (e.g., Trade Proposal creation/submission, DS-API-EXE-005/006), never a confirmation embedded in the chat surface that silently proceeds to execution.

**Acceptance Criteria:**
- No UI treatment of a Sage response includes an affordance that itself submits a consequential action without navigating to that action's own confirmation flow.
- Recommendation language (e.g., "I recommend...") is visually distinct from any confirmed-action state.

**Testing:** UI/behavioral test confirming no consequential action completes directly from the Sage conversational surface without a distinct confirmation event (shared with DS-PRD-005's own test).

### DS-UX-022 — Accessible Interface State Announcements

**Release Classification:** Planned | **Governing Source:** DS-NFR-004, DS-UX-017 (both Planned); DS-UX-016 (Committed, this document — the state model this requirement announces)

**Description:** Once accessibility conformance work is implemented (DS-NFR-004/DS-UX-017), the UI should announce DS-UX-016's interface-state transitions (Loading, Refreshing, Degraded/Partial, Error, Retry/Recovery) to assistive technology (e.g., ARIA live regions or an equivalent mechanism), and should provide non-visual disclosure of stale, partial, degraded, error, and recovery states equivalent to their visual presentation (DS-UX-012's state labeling, DS-UX-015's error content) — an assistive-technology user shall be able to determine the same lifecycle state, data staleness/incompleteness, and available recovery action (e.g., retry) that a sighted user can determine visually, without a separate visual inspection.

**Acceptance Criteria:**
- Entry into each DS-UX-016 lifecycle state (Loading, Refreshing, Degraded/Partial, Error, Retry/Recovery) produces an assistive-technology announcement or equivalent accessible status update.
- A Degraded/Partial or stale-data disclosure (DS-UX-012) is discoverable non-visually, not only through a visual-only indicator.
- Progress/status announcements do not interrupt or override a higher-priority assistive-technology announcement (e.g., an in-progress error dialog), consistent with standard accessible live-region practice.
- This requirement's Planned classification does not make any DS-UX-016 acceptance criterion conditional; DS-UX-016's core lifecycle remains fully Committed/MVP and independently testable regardless of this requirement's implementation status.

**Testing:** Assistive-technology state-announcement test per DS-UX-016 lifecycle state, deferred to this requirement's own implementation timing (tied to DS-NFR-004/DS-UX-017's own tests).

## 11. Non-Goals

DS-007 does not: select a specific component library, CSS/styling framework, or visual design system; define color palette, typography, or brand voice (`docs/standards/BRAND_GUIDE.md`/`STYLE_GUIDE.md`); redesign any DS-004 architectural boundary or DS-006 API contract; commit any UI capability beyond what DS-002 (DS-WKS/DS-USR/DS-NFR) has approved; or make widget/UI visibility itself an enabled-system-capability control (DS-UX-001 fixes this as a permanent constraint, not a current-scope omission).

## 12. Dependencies

- [DS-001](../Volume-01-Foundation/DS-001-Executive-Vision.md), [DS-002](../Volume-02-Product/DS-002-SRS.md) (DS-WKS, DS-USR, DS-NFR, DS-SIG, DS-CHT, DS-OPS families), [DS-004](../Volume-04-Architecture/DS-004-Technical-Architecture.md), [DS-006](../Volume-06-API/DS-006-API-Specification.md)
- `docs/standards/BRAND_GUIDE.md`, `docs/standards/STYLE_GUIDE.md`
- ADR-001, ADR-004

## 13. Risks and Constraints

- **Sequencing:** the Sage-specific explainability/conversational patterns (DS-UX-009's Planned extension, DS-UX-021) are authored ahead of DS-003's Phase 6 implementation; both are Planned and explicitly reference DS-003's own requirements rather than redefining Sage behavior, avoiding a DS-007-owns-Sage-behavior conflict.
- **Classification discipline:** every Committed/MVP `DS-UX-NNN` requirement traces to an already-Committed DS-002/DS-004/DS-006 source; no requirement in this document promotes a Planned upstream item (DS-WKS-002/003/004/005/006, DS-USR-003/004/005, DS-RSK-003, DS-AI/DS-SGE, DS-NFR-004) to Committed. Where a Committed baseline and a Planned extension share one topic (DS-UX-009, DS-UX-011), the two are explicitly separated using the same field-splitting pattern established in DS-005/DS-006 — including DS-UX-016 (Committed core lifecycle) and DS-UX-022 (Planned assistive-technology announcement of that lifecycle), split in the DS-007 accessibility-classification repair to avoid DS-UX-016 depending on the Planned DS-NFR-004/DS-UX-017 accessibility work it had previously cited as a Committed acceptance criterion.

## 14. Verification Approach

Each `DS-UX-NNN` requirement states its own Testing. Document-level verification (unique-ID check, cross-reference consistency against DS-001/DS-002/DS-004/DS-006, no Committed requirement depending on a Planned-only capability) recorded in `.ai-workflow/HANDOFF.md`.

## 15. References

- `docs/codex/Volume-02-Product/requirements/DS-WKS-Workspace-Studio.md`, `DS-USR-Users-and-Onboarding.md`, `DS-NFR-Non-Functional.md`, `DS-SIG-Signal-System.md`, `DS-CHT-Charts.md`, `DS-OPS-Operations.md`
- `docs/codex/Volume-04-Architecture/DS-004-Technical-Architecture.md`
- `docs/codex/Volume-06-API/DS-006-API-Specification.md`
- `docs/standards/BRAND_GUIDE.md`, `docs/standards/STYLE_GUIDE.md`

## Appendix A — Open Questions

1. **Multi-monitor commitment level** — unchanged from DS-002 Appendix A #3; DS-WKS-006/DS-UX-006 remain Future/Exploratory pending an owner decision.
2. **Accessibility standard version** — DS-NFR-004/DS-UX-017 cite WCAG 2.2 Level AA as an example target; formal adoption of a specific standard/version is an owner decision not yet recorded as binding.
3. **Component library / design-system selection** — explicitly out of scope for this document (§11); recorded here so a future DS-007 revision (or a DS-010 standards addition) knows the gap exists.
