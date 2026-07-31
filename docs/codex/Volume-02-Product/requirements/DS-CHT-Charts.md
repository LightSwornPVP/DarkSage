# DS-CHT — Charts

| Field | Value |
|---|---|
| Document ID | DS-CHT |
| Title | Charts |
| Version | 0.2.0 |
| Status | Draft |
| Owner | TheSinnerMan |
| Classification | Internal |
| Repository | LightSwornPVP/DarkSage |
| Created | 2026-07-23 |
| Last Updated | 2026-07-24 |

Parent: [DS-002 — Software Requirements Specification](../DS-002-SRS.md). Requirement conventions defined in DS-002 §5. Charting is named in DS-001 §4 as one of the platform's unifying pillars.

## Requirements

### DS-CHT-001 — Price Charting

**Priority:** High | **Release Classification:** Committed / MVP | **Status:** Draft

**Governing Source:** `ROADMAP.md` Phase 1 ("ChartAdapter interface," "Apache ECharts implementation," "TradingView Lightweight Charts implementation," "Candles," "Volume"); `ARCHITECTURE.md` §9.

**Purpose:** Provide the base visual surface for price/volume analysis that other analytical features build on.

**Description:** DarkSage shall render price charts (at minimum candlestick or OHLC, and volume) for any symbol with available market data (DS-MKT), across a set of Committed/MVP timeframes and date ranges.

**Dependencies:** DS-MKT-001; DS-MKT-002; DS-PRD-008

**Acceptance Criteria:**
- Chart correctly renders available historical and current data for a selected symbol, timeframe, and range.
- Chart indicates data state (current/delayed/stale/historical) consistent with DS-PRD-008.
- Switching timeframe or range does not require leaving the chart view.

**Edge Cases:**
- A symbol with partial historical coverage renders the available portion and discloses the gap rather than failing to render.

**Implementation Notes:** Rendering technology/library choice is a DS-004/DS-007 concern.

**Testing:** Render regression test across supported timeframes, including a data-gap fixture.

### DS-CHT-002 — Technical Indicators and Overlays

**Priority:** Medium | **Release Classification:** Committed / MVP | **Status:** Draft

**Governing Source:** `ROADMAP.md` Phase 1 Quant list (SMA, EMA, RSI, MACD, ATR, Bollinger Bands, VWAP, ADX, OBV, Relative Volume, Relative Strength, "Unit tests against known reference data"); `ARCHITECTURE.md` §8.

**Purpose:** Support standard technical analysis workflows.

**Description:** DarkSage shall allow users to add, configure, and remove technical indicators/overlays (e.g., moving averages, volume-based indicators) on a chart, computed deterministically per DS-PRD-004.

**Dependencies:** DS-CHT-001; DS-PRD-004

**Acceptance Criteria:**
- Indicator values are computed deterministically and reproduce identically given the same input and parameters.
- Users can adjust indicator parameters and see the chart update accordingly.
- Removing an indicator does not alter underlying price data or other active indicators.

**Edge Cases:**
- An indicator requiring more historical data than is available discloses the insufficiency rather than silently computing a misleading value.

**Implementation Notes:** Indicator catalog for MVP is a DS-004/DS-011 sequencing decision.

**Testing:** Deterministic-output regression test per indicator against known fixture data.

### DS-CHT-003 — Chart Annotations

**Priority:** Low | **Release Classification:** Planned | **Status:** Draft

**Purpose:** Let users record their own analysis directly on a chart.

**Description:** DarkSage should allow users to add, edit, and remove manual annotations (trendlines, notes, markers) on a chart, persisted per symbol/chart configuration.

**Dependencies:** DS-CHT-001; DS-USR-002

**Acceptance Criteria:**
- An annotation persists across sessions for the chart/symbol it was created on.
- Annotations do not affect any calculation, indicator, or Sage evidence — user-authored presentation only (DS-PRD-003).

**Edge Cases:**
- An annotation anchored to a date/price remains correctly anchored when the chart is rescaled or the timeframe changes.

**Implementation Notes:** DS-007 concern.

**Testing:** Annotation persistence and rescale-anchoring test.

### DS-CHT-004 — Sage-Chart Evidence Linkage

**Priority:** Medium | **Release Classification:** Planned | **Status:** Draft

**Purpose:** Let Sage reference chart evidence without requiring the chart widget to be visible, per Presentation Independence.

**Description:** DarkSage should allow Sage to reference chart-derived evidence (price levels, indicator values, patterns) regardless of whether a chart widget is currently visible, per DS-PRD-003.

**Dependencies:** DS-PRD-003; DS-PRD-002; DS-CHT-001; DS-AI

**Acceptance Criteria:**
- Sage can cite a chart-derived value with its provenance even when no chart widget is present in the active workspace.
- Hiding the chart widget does not remove chart-derived evidence from Sage's available evidence set.

**Edge Cases:** None beyond those already covered by DS-PRD-002 and DS-PRD-003.

**Implementation Notes:** DS-003/DS-004 concern for evidence-access architecture.

**Testing:** Widget-hidden evidence-availability regression test.

### DS-CHT-006 — Live Trading Workstation Experience

**Priority:** High | **Release Classification:** Planned | **Status:** Draft

**Description:** DarkSage shall support streaming candle formation without manual reload, selectable intervals, extended-hours visibility where provided, last/bid/ask/spread state where licensed, provider/delay/freshness status, synchronized inspection, and overlays for positions, orders, entries, stops, targets, catalysts, support/resistance, and Sage annotations.

**Acceptance Criteria:** Simulated, delayed, stale, and live states are unmistakable; current-candle updates are deterministic from the active feed; chart overlays reference canonical object identifiers rather than copied free text.
