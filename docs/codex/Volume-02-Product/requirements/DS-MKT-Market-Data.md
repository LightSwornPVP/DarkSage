# DS-MKT — Market Data & Intelligence

| Field | Value |
|---|---|
| Document ID | DS-MKT |
| Title | Market Data & Intelligence |
| Version | 0.2.0 |
| Status | Draft |
| Owner | TheSinnerMan |
| Classification | Internal |
| Repository | LightSwornPVP/DarkSage |
| Created | 2026-07-23 |
| Last Updated | 2026-07-24 |

Parent: [DS-002 — Software Requirements Specification](../DS-002-SRS.md). Requirement conventions defined in DS-002 §5. Themed alias: Observatory (DS-001 §17).

## Requirements

### DS-MKT-001 — Market Data Ingestion

**Priority:** Critical | **Release Classification:** Committed / MVP | **Status:** Draft

**Purpose:** Establish a reliable base of market data that the rest of the platform (scanning, charting, risk, backtesting) depends on.

**Description:** DarkSage shall ingest market data (price, volume, and other fields required by Committed/MVP features) from at least one configured data source, normalizing it into a consistent internal representation regardless of source.

**Dependencies:** DS-DAT-001 (local storage baseline); DS-INT (external provider boundary, illustrative — not required to be built for this requirement's own acceptance criteria)

**Acceptance Criteria:**
- Ingested data is normalized to a single internal schema regardless of source vendor, so downstream features do not depend on vendor-specific formats.
- Ingestion failures (feed unavailable, malformed record) are logged (DS-OPS) and do not silently corrupt previously ingested data.
- Ingested records carry a source identifier and ingestion timestamp.

**Edge Cases:**
- Partial/malformed records are rejected individually rather than failing the entire ingestion batch, when the source protocol allows per-record isolation.
- Duplicate records from a redundant feed are deduplicated deterministically.

**Implementation Notes:** Vendor-specific integration detail belongs to DS-INT/DS-006.

**Testing:** Ingestion regression test with valid, malformed, and duplicate fixture records.

### DS-MKT-002 — Historical Market Data

**Priority:** High | **Release Classification:** Committed / MVP | **Status:** Draft

**Governing Source:** `ROADMAP.md` Phase 1 ("historical data ingestion"); `PROJECT_SPEC.md` §32.

**Purpose:** Provide the historical record required for charting, scanning context, and backtesting.

**Description:** DarkSage shall retain and provide access to historical market data for symbols the user has interacted with (watchlisted, charted, backtested), at a granularity sufficient for Committed/MVP charting and backtesting features.

**Dependencies:** DS-MKT-001; DS-CHT; DS-BKT; DS-DAT (local storage)

**Acceptance Criteria:**
- Historical data for a tracked symbol is retrievable for the range required by the requesting feature (e.g., a backtest's configured date range).
- Historical records are immutable once stored, except through an explicit, logged correction process (e.g., a vendor restatement).
- Gaps in historical coverage are discoverable (queryable) rather than silently interpolated as if they were real data.

**Edge Cases:**
- A backtest or chart request for a range with incomplete local history triggers a defined behavior (fetch-if-available, or explicit gap disclosure) rather than silently substituting synthetic data.

**Implementation Notes:** Storage schema/retention policy is a DS-004/DS-005 concern.

**Testing:** Historical-range retrieval test including a fixture with a known data gap.

### DS-MKT-003 — Real-Time and Delayed Data Handling

**Priority:** High | **Release Classification:** Committed / MVP | **Status:** Draft

**Purpose:** Ensure users understand whether the price they are looking at is live.

**Description:** DarkSage shall support both real-time and delayed market data sources and shall clearly and continuously indicate which mode is active for the data currently displayed, per DS-PRD-008.

**Dependencies:** DS-PRD-008; DS-MKT-001; DS-INT

**Acceptance Criteria:**
- Every quote/price surface indicates real-time or delayed status, and the delay duration when delayed (e.g., "delayed 15 min").
- Mode indication updates immediately if the underlying feed's mode changes (e.g., real-time entitlement lapses).
- No Committed/MVP surface presents delayed data without a delay indicator.

**Edge Cases:**
- A symbol with no configured real-time entitlement defaults to delayed mode with disclosure, not to an unlabeled unknown state.

**Implementation Notes:** Entitlement/licensing logic is a DS-INT/DS-006 concern; this requirement governs disclosure obligation only.

**Testing:** Mode-indicator test across delayed and real-time fixture feeds, including a mid-session entitlement change.

### DS-MKT-004 — Data Freshness Thresholds

**Priority:** High | **Release Classification:** Committed / MVP | **Status:** Draft

**Purpose:** Define the concrete staleness behavior referenced generally by DS-PRD-008.

**Description:** DarkSage shall define and apply a per-feed-type staleness threshold beyond which a data value is marked stale, distinct from its normal real-time/delayed status.

**Governing Thresholds (controlled product defaults, added in the DS-002-A04 repair):** Real-time quote (during active market hours): stale if no update within **10 seconds**. Delayed quote: stale if no update within its stated delay window + **60 seconds**. End-of-day/historical candle: stale if not updated within **1 hour after market close** for that session. These are controlled product defaults, configurable per DS-INT-002's integration configuration surface, not values DS-004 chooses unilaterally; DS-004 defines the measurement/enforcement mechanism only.

**Dependencies:** DS-PRD-008; DS-MKT-001; DS-MKT-005 (market calendar awareness)

**Acceptance Criteria:**
- Each feed type has the staleness threshold defined above, or an explicitly configured override, applied consistently.
- A value exceeding its threshold is marked stale in the UI and in any Sage narrative referencing it, distinct from the delayed-mode indicator (DS-MKT-003).
- Staleness evaluation accounts for market-session state (DS-MKT-005) so that closed-market last-known values are not mislabeled as stale during expected non-trading hours.

**Edge Cases:**
- A feed interruption during active trading hours is marked stale within the defined threshold window; the same interruption outside trading hours does not falsely flag staleness.

**Implementation Notes:** DS-004 defines *how* thresholds are measured/enforced; the default numeric values above are the product acceptance target and are not DS-004's to choose.

**Testing:** Staleness-threshold boundary test per feed type, in-session and out-of-session.

### DS-MKT-005 — Market Calendars and Trading Sessions

**Priority:** Medium | **Release Classification:** Committed / MVP | **Status:** Draft

**Purpose:** Give the rest of the platform (freshness logic, scanning, backtesting) an accurate model of when markets are open.

**Description:** DarkSage shall maintain market calendar and trading-session data (regular hours, pre/post-market where applicable, holidays) sufficient to correctly evaluate session state for whatever markets the implementation supports. The specific set of supported markets is an Owner Decision (see DS-002 Appendix A / BLOCKERS.md) and is not fixed by this requirement; this requirement governs correctness of session-state evaluation once that scope is set, not the scope itself.

**Dependencies:** DS-MKT-004 (consumes this requirement's session-state output). Downstream, non-blocking consumers of this data once built: DS-BKT (session-aware backtesting).

**Acceptance Criteria:**
- Session state (pre-market / regular / post-market / closed / holiday) is queryable for any supported market and date, once the supported-market scope is set (Appendix A).
- Calendar data is versioned/updatable to accommodate schedule changes (e.g., holiday calendar updates) without a full application update.

**Edge Cases:**
- A half-trading-day (early close) is represented accurately, not defaulted to a standard full session.

**Implementation Notes:** DS-004/DS-005 concern for storage/update mechanism.

**Testing:** Session-state query test across regular, extended, holiday, and early-close fixtures.

### DS-MKT-006 — Corporate Actions Handling

**Priority:** Medium | **Release Classification:** Planned | **Status:** Draft

**Purpose:** Prevent corporate actions (splits, dividends, symbol changes) from silently corrupting historical continuity or position accuracy.

**Description:** DarkSage should ingest and apply corporate action events (splits, dividends, mergers, symbol/ticker changes) to historical data and affected portfolio positions in a manner that preserves calculation accuracy (DS-PRD-004).

**Dependencies:** DS-MKT-002; DS-PRT; DS-PRD-004

**Acceptance Criteria:**
- A stock split correctly adjusts historical price/volume continuity used by charting and backtesting.
- A dividend event is reflected in realized/unrealized performance calculations (DS-PRT) where applicable.
- A symbol/ticker change preserves the continuity of watchlists, positions, and historical references to the affected security.

**Edge Cases:**
- An unrecognized or malformed corporate action event is flagged for review rather than silently applied.

**Implementation Notes:** Full corporate-action taxonomy and adjustment methodology is a DS-004/DS-005 concern; this requirement establishes the product-level obligation.

**Testing:** Split/dividend/symbol-change fixture regression tests confirming continuity and calculation accuracy.

### DS-MKT-007 — Watchlists

**Priority:** High | **Release Classification:** Planned | **Status:** Draft

**Purpose:** Give users a durable, curated set of symbols to track without re-searching every session.

**Description:** DarkSage should allow users to create, name, edit, and delete one or more watchlists of symbols, each displaying market data fields appropriate to the eventual committed scope for its members.

**Dependencies:** DS-MKT-001; DS-DAT-003 (symbol identity); DS-USR-002 (persistence)

**Acceptance Criteria:**
- A user can add/remove symbols from a named watchlist and the change persists across restarts.
- Multiple watchlists are supported and independently editable.
- A watchlist entry referencing a symbol that becomes invalid/delisted is flagged rather than silently removed.

**Edge Cases:**
- Adding a duplicate symbol to the same watchlist is a no-op rather than creating a duplicate entry.
- A watchlist with zero members renders as an empty, still-usable list rather than an error state.

**Implementation Notes:** DS-004/DS-005 concern for storage.

**Testing:** Watchlist CRUD regression test; delisted-symbol flag test.
