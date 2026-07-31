# DS-USR — Users, Personas & Onboarding

| Field | Value |
|---|---|
| Document ID | DS-USR |
| Title | Users, Personas & Onboarding |
| Version | 0.2.0 |
| Status | Draft |
| Owner | TheSinnerMan |
| Classification | Internal |
| Repository | LightSwornPVP/DarkSage |
| Created | 2026-07-24 |
| Last Updated | 2026-07-24 |

Parent: [DS-002 — Software Requirements Specification](../DS-002-SRS.md). Requirement conventions, ID scheme, and Release Classification definitions are defined in DS-002 §5 and are not repeated here.

## Requirements

### DS-USR-001 — First-Run Onboarding

**Priority:** High | **Release Classification:** Planned | **Status:** Draft

**Purpose:** Give a new user a working, understood starting point instead of an empty or overwhelming workspace.

**Description:** On first run, DarkSage shall present an onboarding flow that establishes a default workspace layout, terminology mode preference (DS-USR-003), and a minimal set of required preferences before routing the user into the main workspace.

**Dependencies:** DS-PRD-010 (Application Startup); DS-WKS (default layout); DS-USR-003

**Acceptance Criteria:**
- A user with no prior profile is routed to onboarding rather than an empty or default-config workspace.
- Onboarding completes in a bounded number of steps and can be skipped to safe defaults without blocking access to the workspace.
- Skipping onboarding does not leave the application in an unusable or ambiguous state; documented defaults apply.

**Edge Cases:**
- A user who exits mid-onboarding resumes at the same step on next launch rather than restarting or losing partial input.
- Onboarding does not require network/external-service access to reach a usable local workspace.

**Implementation Notes:** Exact onboarding screens/flow belong to DS-007 (UI/UX). This requirement constrains outcome (a usable, understood starting state), not visual design.

**Testing:** First-run test on a clean profile; skip-path test; interrupted-onboarding resume test.

### DS-USR-002 — User Preferences Persistence

**Priority:** High | **Release Classification:** Planned | **Status:** Draft

**Purpose:** Ensure a user's choices persist across sessions so the product does not reset itself.

**Description:** DarkSage shall persist user preferences (terminology mode, workspace defaults, notification settings, and other user-configurable options defined by other requirement families) locally across application restarts.

**Dependencies:** DS-DAT (local storage); DS-USR-003; DS-WKS

**Acceptance Criteria:**
- A preference change survives an application restart without requiring the user to reconfigure it.
- Preference storage is local by default, consistent with DS-001 §14's local-first preference.
- Corrupted or unreadable preference storage falls back to documented safe defaults rather than crashing the application.

**Edge Cases:**
- Concurrent preference edits from multiple open workspace surfaces (if supported) resolve deterministically rather than silently discarding one edit.
- A preferences schema migration (e.g., after an application update) preserves recognizable prior values or explicitly resets with user notice.

**Implementation Notes:** Storage format/location is a DS-004/DS-005 concern.

**Testing:** Restart-persistence test; corrupted-storage recovery test.

### DS-USR-003 — Professional and Codex-Themed Terminology Modes

**Priority:** Medium | **Release Classification:** Planned | **Status:** Draft

**Purpose:** Let users choose plain professional language or DarkSage's Codex-themed vocabulary without being forced to learn either to use the product, per DS-001 §17.

**Description:** DarkSage shall provide a user-selectable terminology mode (professional / Codex-themed) that governs the display labels used for themed concepts (e.g., Observatory/Market Data, Watchtower/Scanner, Forge/Strategy Builder, Chronicle/Backtesting, Guardian/Risk Engine, Treasury/Portfolio, Sage/AI Assistant) without altering underlying functionality.

**Dependencies:** DS-001 §17; DS-USR-002 (persistence)

**Acceptance Criteria:**
- Switching terminology mode changes only display labels and in-product copy; it does not change enabled capability, data, or calculation results (consistent with DS-PRD-003's principle that presentation is separate from capability).
- Both modes remain immediately understandable; themed labels are never the *only* label for a professional financial concept without an accessible plain-language equivalent (e.g., tooltip, settings mapping).
- The selected mode persists per DS-USR-002.

**Edge Cases:**
- Mixed content (e.g., a saved report authored under one mode) remains readable and correctly labeled if viewed after a mode switch.
- Sage's own conversational output respects the active terminology mode for consistency.

**Implementation Notes:** The mapping table is defined once in DS-001 §17 / `docs/standards/STYLE_GUIDE.md`; this requirement does not redefine it, only requires it be user-selectable and enforced consistently.

**Testing:** Mode-switch regression test across every themed label in the current MVP surface, verifying no functional change accompanies the label change.

### DS-USR-004 — Capability-Based User Personas

**Priority:** Medium | **Release Classification:** Planned | **Status:** Draft

**Purpose:** Give onboarding and default configuration a reasonable starting point without hard-limiting any user's access to capability.

**Description:** DarkSage should offer capability-based starting-point presets (developing/self-directed investor, active trader, advanced/professional-style user, per DS-002 §8) that adjust default workspace density and terminology mode suggestion, without restricting access to any enabled capability regardless of the selected persona.

**Dependencies:** DS-002 §8; DS-USR-001; DS-USR-003; DS-WKS

**Acceptance Criteria:**
- Selecting a persona preset changes only default presentation (initial layout density, suggested terminology mode); it does not enable or disable any analytical capability.
- A user may change or abandon their initial persona preset at any time without data loss or re-onboarding.
- No capability is gated behind a persona selection (consistent with DS-001 §18's rejection of artificial capability limits).

**Edge Cases:**
- A user who selects "beginner"-oriented presets and later wants full analytical depth reaches it through normal settings/workspace customization, not a hidden unlock mechanism.

**Implementation Notes:** Persona presets are a convenience default, not an access-control mechanism; DS-004/DS-007 own the implementation.

**Testing:** Preset-selection test confirming identical capability surface across all personas, differing only in default presentation.

**Future Enhancements:** Persona-informed contextual education suggestions (tied to the Trading Knowledge Engine direction, DS-001 §19.2) are Future/Exploratory pending a dedicated requirement family.

### DS-USR-005 — Progressive Disclosure of Advanced Capability

**Priority:** Medium | **Release Classification:** Planned | **Status:** Draft

**Purpose:** Keep default views approachable while ensuring advanced users are not blocked from depth.

**Description:** DarkSage shall present advanced/power-user configuration and analytical depth through progressive disclosure (secondary panels, expandable detail, advanced settings) rather than by removing the capability from the product.

**Dependencies:** DS-001 §19, §18; DS-WKS

**Acceptance Criteria:**
- Every Committed/MVP analytical capability is reachable by an advanced user without requiring a workspace rebuild from scratch.
- Default views do not surface every available control simultaneously; advanced controls are discoverable (e.g., an "advanced" affordance) rather than hidden without indication.

**Edge Cases:**
- A capability reachable only through progressive disclosure remains available to Sage regardless of disclosure state (DS-PRD-003).

**Implementation Notes:** Concrete UI patterns belong to DS-007.

**Testing:** Usability walkthrough confirming default view is uncluttered and advanced view exposes full Committed/MVP capability.

### DS-USR-006 — Local User Profile Identity

**Priority:** Medium | **Release Classification:** Planned | **Status:** Draft

**Purpose:** Establish a minimal identity concept sufficient to scope preferences, workspaces, and data without requiring a mandatory external account.

**Description:** DarkSage shall support a local user profile sufficient to scope preferences and workspace state (DS-USR-002, DS-WKS) without requiring creation of an external/cloud account as a precondition for core local functionality.

**Dependencies:** DS-001 §14 (local-first); DS-DAT; DS-SEC

**Acceptance Criteria:**
- Core local functionality (workspace use, local data analysis, backtesting on locally available data) is reachable without an external account.
- Any optional external/cloud account remains explicitly opt-in and is not silently required by a Committed/MVP capability.

**Edge Cases:**
- Multiple local profiles on one machine, if supported, do not cross-contaminate preferences or data between profiles.

**Implementation Notes:** Multi-profile support beyond a single default profile is Planned unless a dedicated requirement commits it; single-profile local identity is Committed/MVP.

**Testing:** Offline/no-account functional test confirming core local capability is reachable.
