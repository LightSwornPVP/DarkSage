# DS-ALT — Alerts & Monitoring

| Field | Value |
|---|---|
| Document ID | DS-ALT |
| Title | Alerts & Monitoring |
| Version | 0.2.0 |
| Status | Draft |
| Owner | TheSinnerMan |
| Classification | Internal |
| Repository | LightSwornPVP/DarkSage |
| Created | 2026-07-24 |
| Last Updated | 2026-07-24 |

Parent: [DS-002 — Software Requirements Specification](../DS-002-SRS.md). Requirement conventions defined in DS-002 §5.

## Requirements

### DS-ALT-001 — User-Configured Alerts

**Priority:** High | **Release Classification:** Planned | **Status:** Draft

**Purpose:** Let users be notified of conditions they care about without continuously watching the screen.

**Description:** DarkSage shall allow users to configure alerts on market data conditions (e.g., price/indicator thresholds), watchlist events, or risk-limit conditions (DS-RSK-003), and shall notify the user when a configured condition is met.

**Dependencies:** DS-MKT-001; DS-RSK-003; DS-PRD-007

**Acceptance Criteria:**
- A configured alert fires a notification when its condition is met, evaluated against current/available data.
- Alert firing never places, schedules, or queues a trade — notification only (DS-PRD-007).
- A fired alert is recorded (timestamp, condition, triggering value) and reviewable by the user.

**Edge Cases:**
- An alert condition dependent on stale/delayed data discloses that state alongside the notification (DS-PRD-008).
- Duplicate rapid-fire triggering of the same condition (e.g., price oscillating around a threshold) is deduplicated per a documented cooldown rule rather than flooding the user.

**Implementation Notes:** DS-004 concern for the alert evaluation engine.

**Testing:** Alert trigger regression test including stale-data and oscillation fixtures.

### DS-ALT-002 — Notification Delivery

**Priority:** Medium | **Release Classification:** Planned | **Status:** Draft

**Purpose:** Ensure a fired alert actually reaches the user in a usable way.

**Description:** DarkSage shall deliver alert notifications through at least one in-application surface, reliably reflecting alert state regardless of active workspace layout (DS-PRD-003).

**Dependencies:** DS-ALT-001; DS-PRD-003

**Acceptance Criteria:**
- A fired alert is visible in the application regardless of which workspace/widgets are currently displayed.
- Notification history is retrievable after the triggering moment has passed.

**Edge Cases:**
- The application being closed/backgrounded at fire time results in the notification being visible on next open, not lost.

**Implementation Notes:** External notification channels (OS-level, email, push) beyond in-app delivery are Planned (DS-ALT-003).

**Testing:** Notification-visibility test across workspace states; missed-notification recovery-on-reopen test.

### DS-ALT-003 — External Notification Channels

**Priority:** Low | **Release Classification:** Planned | **Status:** Draft

**Purpose:** Reach users when the application is not open.

**Description:** DarkSage should support optional delivery of alert notifications through external channels (e.g., OS-level notification, email) as user-configured, opt-in extensions of DS-ALT-002.

**Dependencies:** DS-ALT-002; DS-SEC

**Acceptance Criteria:**
- External channel delivery is opt-in and disabled by default.
- Configuring an external channel does not expose alert content beyond what the user has explicitly enabled for that channel.

**Edge Cases:**
- External channel delivery failure does not suppress the in-app notification (DS-ALT-002 remains authoritative).

**Implementation Notes:** DS-INT/DS-008 concern for channel integration and credential handling.

**Testing:** Opt-in default test; external-channel-failure fallback test.
