# DarkSage TradingView Capability Comparison

| Field | Value |
|---|---|
| Document | TradingView Capability Comparison |
| Version | 0.1.0 |
| Status | Draft (Foundation Pass) |
| Owner | TheSinnerMan |
| Owning Volume | DS-022 (`docs/codex/Volume-22-ProductExperience/`) |
| Created | 2026-07-25 |
| Last Updated | 2026-07-25 |

DarkSage does not attempt full TradingView parity before initial release. This document classifies every TradingView-comparable capability named in the Product Expansion foundation instructions so none is silently omitted, and so the difference between "deferred" and "rejected" is always explicit. Every `feature_id` below was looked up directly against `FEATURE_REGISTRY.csv`, not guessed.

## Classifications

- **A — Required for initial release** (Stage 5)
- **B — Required for Founder beta but not initial alpha** (Stage 3, not Stage 2)
- **C — Deferred but groundwork required now** (later stage, `groundwork_required_now = Groundwork Required Now`)
- **D — Long-term backlog** (later stage, `groundwork_required_now = Can Be Added Later Without Current Architectural Work`, or `Decision Pending`)
- **E — Explicitly rejected or restricted** (never planned under current governance, or restricted to a specific, named scope)

## Charting

| Capability | Class | feature_id | Notes |
|---|---|---|---|
| Professional candlestick charts | A | FEAT-0020 | Stage 2, initial_release_required=Yes. |
| Indicator panes | A | FEAT-0021 | Stage 2, initial_release_required=Yes. |
| Saved chart layouts | B | FEAT-0022 | Reclassified from C (2026-07-26 audit repair): release_stage=Stage 3 (Founder Workstation Beta), initial_release_required=No -- required for Founder beta, not initial customer alpha/release. |
| Chart templates | D | FEAT-0023 | Can be added later. |
| Multi-chart layouts | C | FEAT-0024 | Groundwork Required Now (layout model). |
| Synchronized symbols | C | FEAT-0025 | Depends on multi-chart layouts. |
| Synchronized crosshairs | C | FEAT-0026 | Depends on multi-chart layouts. |
| Multi-monitor workspaces | C | FEAT-0027 | Groundwork Required Now (workspace/layout model), Windows-only for now. |
| Advanced chart types (Heikin-Ashi, Renko, etc.) | D | FEAT-0028 | Can be added later. |
| Chart-layout synchronization (cloud) | C | FEAT-0029 | Groundwork Required Now (local/cloud sync model, DS-017). |
| Chart snapshots | D | FEAT-0030 | Can be added later. |
| Chart-based order placement | C | FEAT-0031 | Groundwork Required Now (must integrate with deterministic validation). |
| Draggable stops and targets | C | FEAT-0032 | Groundwork Required Now; must never bypass deterministic validation. |

## Drawing Tools

| Capability | Class | feature_id | Notes |
|---|---|---|---|
| Trend lines | B | FEAT-0033 | Reclassified from C (2026-07-26 audit repair): Stage 3 Founder-beta requirement, not Stage 5. |
| Horizontal and vertical levels | B | FEAT-0034 | Reclassified from C (2026-07-26 audit repair): Stage 3 Founder-beta requirement, not Stage 5. |
| Channels | C | FEAT-0035 | Groundwork Required Now (shared drawing model). |
| Fibonacci tools | C | FEAT-0036 | Groundwork Required Now (shared drawing model). |
| Support and resistance | C | FEAT-0037 | Groundwork Required Now (shared drawing model). |
| Anchored VWAP | C | FEAT-0038 | Groundwork Required Now (shared drawing model). |
| Risk/reward tools | C | FEAT-0039 | Groundwork Required Now; ties into exit-plan model (DS-020). |
| Long-position planner | C | FEAT-0040 | Groundwork Required Now; informational only, never bypasses validation. |
| Short-position planner | C | FEAT-0041 | Groundwork Required Now; informational only, never bypasses validation. |
| Notes and callouts | D | FEAT-0042 | Can be added later. |
| Drawing templates | D | FEAT-0043 | Can be added later. |
| Drawing locking and hiding | D | FEAT-0044 | Can be added later. |
| Drawing synchronization (cloud) | C | FEAT-0045 | Groundwork Required Now (DS-017 sync model). |
| Drawing-based alerts | C | FEAT-0046 | Groundwork Required Now (ties drawing model to alert engine). |
| Drawing persistence architecture | C | FEAT-0047 | The specific groundwork item underlying every drawing tool above. |

## Screeners

| Capability | Class | feature_id | Notes |
|---|---|---|---|
| Stock screener | A | FEAT-0058 | Stage 5, initial_release_required=Yes. |
| ETF screener | A | FEAT-0059 | Stage 5, initial_release_required=Yes. |
| Options screener | C | FEAT-0060 | Blocked on options-data-provider selection; groundwork tracked now. |
| Technical filters | A | FEAT-0061 | Stage 5, initial_release_required=Yes. |
| Fundamental filters | A | FEAT-0062 | Stage 5, initial_release_required=Yes. |
| Custom columns | D | FEAT-0063 | Can be added later. |
| Saved templates | D | FEAT-0064 | Can be added later. |
| Scan scheduling | D | FEAT-0065 | Can be added later. |
| Scan history | D | FEAT-0066 | Can be added later. |
| Strategy-based scans | C | FEAT-0067 | Groundwork Required Now (ties into strategy-language sandbox). |
| Export | D | FEAT-0068 | Can be added later. |
| Future forex/futures/crypto/bond/global-equity screening | D | FEAT-0069 | Long-term backlog, tied to Asset-Class Roadmap. |

## Watchlists

| Capability | Class | feature_id | Notes |
|---|---|---|---|
| Multiple watchlists | A | FEAT-0048 | Stage 2, initial_release_required=Yes. |
| Grouped watchlists | D | FEAT-0049 | Can be added later. |
| Color labels | D | FEAT-0050 | Can be added later. |
| Smart watchlists | A | FEAT-0051 | Stage 5, initial_release_required=Yes; groundwork now (rule engine). |
| Sage-generated watchlists | C | FEAT-0052 | Reclassified from D (2026-07-26 audit repair): groundwork_required_now=Groundwork Required Now in the registry (depends on Customer Cloud Sage groundwork). |
| Catalyst badges | D | FEAT-0053 | Can be added later. |
| Earnings badges | D | FEAT-0054 | Can be added later. |
| Broker synchronization | D | FEAT-0055 | Can be added later. |
| Import and export | D | FEAT-0056 | Can be added later. |
| Watchlist-wide alerts | C | FEAT-0057 | Groundwork Required Now (ties into alert-condition model). |

## Alerts

| Capability | Class | feature_id | Notes |
|---|---|---|---|
| Price alerts | A | FEAT-0070 | Stage 5, initial_release_required=Yes. |
| Indicator alerts | A | FEAT-0071 | Stage 5, initial_release_required=Yes. |
| Strategy alerts | A | FEAT-0072 | Stage 5, initial_release_required=Yes. |
| Drawing alerts | C | FEAT-0073 | Groundwork Required Now (depends on drawing persistence). |
| Watchlist alerts | C | FEAT-0074 | Groundwork Required Now. |
| Portfolio alerts | A | FEAT-0075 | Stage 5, initial_release_required=Yes. |
| Risk alerts | A | FEAT-0076 | Stage 5, initial_release_required=Yes; Deterministic-Authoritative. |
| Broker-state alerts | C | FEAT-0077 | Groundwork Required Now (operational observability, DS-023). |
| Data-quality alerts | A | FEAT-0078 | Data-layer already tested (freshness); product surface required for Stage 5. |
| Multi-condition alert builder | C | FEAT-0079 | Groundwork Required Now (advanced alert condition model). |
| Alert suppression | D | FEAT-0080 | Can be added later. |
| Cooldowns | A | FEAT-0081 | Stage 5, initial_release_required=Yes. |
| Escalation | D | FEAT-0082 | Can be added later. |
| Acknowledgement | D | FEAT-0083 | Can be added later. |
| Alert history | A | FEAT-0084 | Stage 5, initial_release_required=Yes. |
| Mobile/desktop/email/notification delivery | A | FEAT-0085 | Stage 5, initial_release_required=Yes. |
| Discord (notification-only) | D | FEAT-0086 | Already-approved boundary (DS-ALT-004/DS-INT-006); never a control channel. |
| Signed generic webhooks (future) | C | FEAT-0087 | Groundwork Required Now (signing/delivery infrastructure), delivery itself deferred. |

## Market Visualization

| Capability | Class | feature_id | Notes |
|---|---|---|---|
| S&P 500 heatmap | C | FEAT-0109 | Groundwork Required Now (DS-VIZ family, DS-022). |
| Sector heatmap | C | FEAT-0110 | Groundwork Required Now. |
| Industry heatmap | C | FEAT-0111 | Groundwork Required Now. |
| Portfolio heatmap | C | FEAT-0112 | Groundwork Required Now. |
| Risk-concentration heatmap | C | FEAT-0113 | Groundwork Required Now; Deterministic-Authoritative underlying data. |
| Correlation heatmap | C | FEAT-0114 | Groundwork Required Now. |
| Implied-volatility heatmap | C | FEAT-0115 | Groundwork Required Now; blocked on options data. |
| Strategy-opportunity heatmap | C | FEAT-0116 | Groundwork Required Now; Advisory only. |
| Market breadth | C | FEAT-0117 | Groundwork Required Now. |
| Advance/decline data | C | FEAT-0118 | Groundwork Required Now. |
| New highs and lows | C | FEAT-0119 | Groundwork Required Now. |
| Sector rotation | C | FEAT-0120 | Groundwork Required Now. |
| Market-regime dashboard | C | FEAT-0121 | Groundwork Required Now; Advisory (Sage-informed). |

## News and Calendars

| Capability | Class | feature_id | Notes |
|---|---|---|---|
| Symbol news | A | FEAT-0088 | Stage 5, initial_release_required=Yes. |
| Portfolio news | A | FEAT-0089 | Stage 5, initial_release_required=Yes. |
| Breaking-news mode | D | FEAT-0090 | Can be added later. |
| Duplicate-story clustering | D | FEAT-0091 | Can be added later. |
| Source reliability | D | FEAT-0092 | Can be added later. |
| Sentiment | D | FEAT-0093 | Can be added later; Advisory only. |
| Catalyst extraction | D | FEAT-0094 | Can be added later; Advisory only. |
| Rumor vs. confirmed labeling | D | FEAT-0095 | Can be added later. |
| Chart news markers | C | FEAT-0096 | Groundwork Required Now (chart-overlay model). |
| Economic calendar | D | FEAT-0097 | Reclassified from A (2026-07-26 audit repair): registry initial_release_required=No, groundwork=Can Be Added Later; distinct from Earnings calendar (FEAT-0098), which is genuinely initial_release_required=Yes. |
| Earnings calendar | A | FEAT-0098 | Stage 5, initial_release_required=Yes. |
| Dividend calendar | D | FEAT-0099 | Can be added later. |
| Split calendar | D | FEAT-0100 | Can be added later. |
| IPO calendar | D | FEAT-0101 | Can be added later. |
| Options expiration calendar | C | FEAT-0102 | Groundwork Required Now; blocked on options data. |
| Federal Reserve events | D | FEAT-0103 | Can be added later. |
| Treasury events | D | FEAT-0104 | Can be added later. |
| Market holidays | A | FEAT-0105 | Stage 2, initial_release_required=Yes. |
| Early closes | A | FEAT-0106 | Stage 2, initial_release_required=Yes. |
| Trading halts | C | FEAT-0107 | Groundwork Required Now; Deterministic-Authoritative (halted symbol must not silently allow orders). |
| Strategy blackout periods | C | FEAT-0108 | Groundwork Required Now; Deterministic-Authoritative. |

## Advanced Market Tools

| Capability | Class | feature_id | Notes |
|---|---|---|---|
| Level II | D | FEAT-0193 | Can be added later. |
| Depth of Market | D | FEAT-0194 | Can be added later. |
| Time and sales | D | FEAT-0195 | Can be added later. |
| Order ladder | C | FEAT-0196 | Groundwork Required Now; Deterministic-Authoritative execution path. |
| Hotkeys | D | FEAT-0197 | Can be added later; Deterministic-Authoritative execution path regardless. |
| Hotkey safety | C | FEAT-0198 | Groundwork Required Now (must exist before hotkeys ship, not after). |
| Order templates | D | FEAT-0199 | Can be added later. |
| Partial-fill visualization | D | FEAT-0200 | Can be added later. |
| Bracket visualization | D | FEAT-0201 | Reclassified from A (2026-07-26 audit repair, see FEATURE_REGISTRY.csv release_history): initial_release_required changed Yes -> No, release_stage changed Stage 5 -> Stage 6 -- brackets themselves (FEAT-0170/FEAT-0171) are release-required; the dedicated visualization overlay is not. |

## Strategy Customization

| Capability | Class | feature_id | Notes |
|---|---|---|---|
| Restricted DarkSage strategy language | C | FEAT-0131 | Groundwork Required Now; Deterministic-Authoritative sandbox boundary. |
| Visual strategy builder | C | FEAT-0132 | Groundwork Required Now; depends on the restricted strategy language. |
| Indicator builder | C | FEAT-0133 | Groundwork Required Now; same sandbox. |
| Alert builder (strategy-linked) | C | FEAT-0134 | Groundwork Required Now; same sandbox. |
| Founder-only Python research extensions | B | FEAT-0135 | Reclassified from C (2026-07-26 audit repair): Stage 3 Founder Workstation Beta target, Founder-private workstation/development environment only (see FEATURE_REGISTRY.csv platform_availability); never customer-available. |
| Versioned strategies | D | FEAT-0136 | Already Planned at Stage 2 (can be added within existing architecture). |
| Versioned indicators | D | FEAT-0137 | Already Planned at Stage 2. |
| Safety scanning | C | FEAT-0138 | Groundwork Required Now; Critical priority, Deterministic-Authoritative. |
| No arbitrary customer code in deterministic execution | A | FEAT-0139 | Designed, not Implemented (2026-07-26 audit repair): ADR-002 documents the invariant; no live implementation exists yet in backend/. |
| No script bypass of risk validation | A | FEAT-0140 | Designed, not Implemented (2026-07-26 audit repair): ADR-002 documents the invariant; no live implementation exists yet in backend/. |
| Founder Sage Developer Mode (private coding/research tooling) | B | FEAT-0268 | New (2026-07-26 audit repair): Founder-only, private, local-workstation capability; groundwork begins Stage 1, usable private version targeted for Stage 3 Founder Workstation Beta; never customer-available. See DS-018 (owner), DS-015/DS-021/DS-023 (supporting). |

## Community and Ecosystem

| Capability | Class | feature_id | Notes |
|---|---|---|---|
| Private collaboration | C | FEAT-0217 | Reclassified from D (2026-07-26 audit repair): registry groundwork_required_now=Groundwork Required Now (permissions model needed now even though the feature itself is Stage 8 backlog). |
| Shared research | C | FEAT-0218 | Reclassified from D (2026-07-26 audit repair): registry groundwork_required_now=Groundwork Required Now. |
| Shared watchlists (private) | C | FEAT-0219 | Reclassified from D (2026-07-26 audit repair): registry groundwork_required_now=Groundwork Required Now. |
| Private teams | C | FEAT-0220 | Groundwork Required Now (permissions model), feature itself Stage 8. |
| Paper-trading competitions | D | FEAT-0221 | Stage 8 backlog. |
| Creator profiles | C | FEAT-0222 | Groundwork Required Now (identity/ownership model). |
| Strategy distribution | C | FEAT-0223 | Groundwork Required Now (versioning/ownership model). |
| Verified performance | C | FEAT-0224 | Groundwork Required Now — **no performance claim may launch without this**. |
| Public marketplace (long-term backlog) | D | FEAT-0225 | Stage 9, long-term backlog. |
| Anonymous public copy trading at launch | E | FEAT-0226 | Explicitly rejected at launch. |
| Public paid signal marketplace at launch | E | FEAT-0227 | Explicitly rejected at launch. |

## Asset-Class Roadmap

| Capability | Class | feature_id | Notes |
|---|---|---|---|
| U.S. stocks and ETFs | A | FEAT-0010 | Stage 5, initial_release_required=Yes. |
| U.S. listed options | A | FEAT-0011 | Stage 5, initial_release_required=Yes (selected intelligence only). |
| Indexes | A | FEAT-0009 | Covered by the core quote/candle data feed. |
| Crypto observation and paper trading | D | FEAT-0012 | Stage 6 backlog. |
| Futures | D | FEAT-0013 | Stage 7 backlog. |
| Forex | D | FEAT-0014 | Stage 7 backlog. |
| International equities | D | FEAT-0015 | Stage 8 backlog. |
| Bonds and fixed income | D | FEAT-0016 | Stage 9, Decision Pending. |
| Macroeconomic datasets | D | FEAT-0017 | Stage 8, Decision Pending. |
| On-chain data | D | FEAT-0018 | Stage 9, Decision Pending. |

## Cross-Cutting Rule

**No deferred feature above is marked a release blocker unless its own groundwork is genuinely missing** — every "C" (groundwork-required) row states specifically what groundwork it needs; every "D" row is deferred purely on priority/sequencing, not on a missing architectural dependency.

## Revision History

| Version | Date | Summary |
|---|---|---|
| 0.1.0 | 2026-07-25 | Initial foundation-pass classification of every TradingView-comparable capability named in the Product Expansion foundation instructions. |
