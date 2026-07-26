# DarkSage Founder Idea Coverage Report

| Field | Value |
|---|---|
| Document ID | DEV-COVERAGE-001 |
| Version | 1.1.0 |
| Status | Draft — for Founder review |
| Baseline | `34a65818d48f596122281075e18c6e5f36ec93b5` |

Every idea below appears in the controlled documentation set (a requirement, DS-013 backlog entry, DS-014 idea, or a documented Open Question) — none is Rejected/Not Pursuing at this baseline. Status vocabulary (Committed/MVP, Planned, Candidate, Approved Future, Research Needed, Exploratory) is quoted verbatim from source, not inferred. "Blocks Next Slice" refers to [[DARKSAGE_NEXT_IMPLEMENTATION_SLICE]] (backtest-result persistence) — none of these ideas block it, since that slice only touches Phase 2/3 backtesting persistence.

| # | Idea Category | Current Location | Controlling ID/Status | Coverage | Recommended Destination | Founder Decision Required |
|---|---|---|---|---|---|---|
| 1 | Product identity/branding | DS-001 Foreword, §4 | DS-001, Approved | Fully Covered | Already correct | No |
| 2 | Sage core capability | `DS-AI-Sage.md` DS-AI-001–007; DS-003 DS-SGE-001–020 | Planned (Phase 6); safety boundaries Committed/MVP | Fully Covered | Already correct | No |
| 3 | Full automation (paper + live) | DS-EXE-001/002/003/006/007; `ROADMAP.md` Phase 7/13–14; DS-013 DS-BL-001/025 | DS-EXE-001/007 Committed/MVP; DS-EXE-002/003/006 Planned; DS-BL-001/025 Approved Future; live full-auto Future/Exploratory | Partially Covered — paper path governed; live full-auto not yet approved | Already correct (paper); DS-013 backlog (live extension) — see [[DARKSAGE_FULL_AUTO_TRADING_MODES]] | No — addressed by this pass's controlled update |
| 4 | Trade intelligence (signals/ratings) | DS-SCN-001/002/003, DS-SIG-001/002/003 | Committed/MVP | Fully Covered | Already correct | No |
| 5 | Strategy intelligence (creation/backtesting/promotion) | DS-STR-001–003, DS-BKT-001–004, DS-PERF-001–004, DS-ARC-020; DS-013 DS-BL-005/006 | Planned; DS-BL-005 Planned, DS-BL-006 Candidate | Fully Covered | Already correct | No |
| 6 | Research sources (news/fundamentals/sentiment/macro/alt-data) | PRS §9.9; DS-013 DS-BL-010; DS-014 DS-IDEA-012/013; ROADMAP Phase 10 | DS-BL-010 Candidate; DS-IDEA-012/013 Exploratory; Phase 10 items have no DS-002 requirement yet | Partially Covered — every sub-area tracked, none Committed/Planned | Already correct — appropriately unpromoted | No |
| 7 | Portfolio management | DS-PRT-001–004; DS-013 DS-BL-023 | Planned | Fully Covered | Already correct | No |
| 8 | Trading journal | `DS-JRN-Journal-and-Review.md` DS-JRN-001–006 | Planned; DS-JRN-006 Future/Exploratory | **Now Fully Covered** — closed by the Founder Vision Completion pass (2026-07-25) | Already correct | No — resolved |
| 9 | UI/UX general | DS-UX-001/009/012/016/017/022; ADR-004; DS-PRD-003 | DS-UX-016 Committed/MVP; others Planned | Fully Covered | Already correct | No |
| 10 | Safety/execution controls | DS-EXE-001, DS-RSK-001/002, DS-EXE-004/005; TRADING_RULES.md | Committed/MVP core; DS-EXE-004/005 Planned | Fully Covered | Already correct | No |
| 11 | Social/gamification features | DS-013 DS-BL-012/013 | Candidate; DS-BL-013 "leans toward Rejected pending owner review" | Partially Covered — tensions with DS-001 §9 anti-engagement stance | Genuine Open Question (DS-013 Appendix A #1) | **Yes** |
| 12 | Education/learning content | `DS-EDU-Trading-Knowledge.md` DS-EDU-001/002 | DS-EDU-001 Planned; DS-EDU-002 Future/Exploratory | Fully Covered | Already correct | No |
| 13 | Tax reporting | DS-013 DS-BL-011 (bundled with budgeting); ROADMAP Phase 14 | Candidate | Partially Covered — bundled despite differing legal risk | DS-013 backlog — recommend splitting from budgeting | **Yes** |
| 14 | Budgeting | Same DS-013 DS-BL-011; DS-013 Appendix A #2 notes product-identity fit "unresolved" | Candidate | Distorted/Duplicated — conflated with tax reporting | Genuine Open Question (DS-013 Appendix A #2) | **Yes** — is budgeting even in-identity for a trading-intelligence product |
| 15 | Asset class expansion (options/futures/crypto/forex) | DS-013 DS-BL-007 (options), DS-BL-008 (futures), DS-BL-009 (crypto); no forex entry found | DS-BL-007 Deferred; DS-BL-008/009 Research Needed | Fully Covered (options/futures/crypto); **Missing** (forex) | Already correct; forex needs a new DS-013 entry if desired | No |
| 16 | Provider expansion (brokers/data/AI) | DS-013 DS-BL-002/003; DS-ARC-006/013/015 | DS-BL-002 Planned; DS-BL-003 Approved Future; DS-ARC-006/015 Committed/MVP; DS-ARC-013 Planned | Fully Covered | Already correct | No |
| 17 | Market-model research (foundation/specialized models) | DS-013 DS-BL-018/019/020/021; DS-014 DS-IDEA-001–006/019/020/025; DS-011 DS-RM-009 | Research Needed / Exploratory, gated by DS-IDG-004's nine gates | Fully Covered | Already correct | No |
| 18 | Deployment/hardware (local vs hosted, GPU sizing) | ARCHITECTURE.md §27/§29; PROJECT_SPEC.md §2.1; PRS §22 Open Questions #7/#8 | Stage model documented; hosting/DB-trigger open; no GPU/hardware-sizing requirement found | Partially Covered — no hardware-sizing requirement exists | Genuine Open Question / new DS-013 entry | **Yes** |
| 19 | Business model / premium tiers / monetization | DS-013 DS-BL-026 | Candidate; "Entire business model undecided" | Partially Covered | Genuine Open Question | **Yes** |
| 20 | Mobile control/monitoring | `DS-MOB-Mobile-Client.md` DS-MOB-001/002/003; ROADMAP Phase 9; DS-013 DS-BL-015; ARCHITECTURE.md §26 | DS-MOB-002 Committed/MVP; DS-MOB-001/003 Planned; DS-BL-015 Approved Future | Fully Covered | Already correct | No |
| 21 | Skeleton loaders | DS-013 DS-BL-027 §6.15; DS-UX-016; PRS §9.22 | DS-BL-027 Approved Future; DS-UX-016 Committed/MVP | Fully Covered | DS-013 backlog (ripe for promotion to a dedicated DS-007 requirement) | No |
| 22 | Caching strategy | Same DS-BL-027 entry | Approved Future | Fully Covered | Same as row 21 | No |
| 23 | Optimistic rendering | Same DS-BL-027 entry, incl. explicit Hard Safety Boundary (never for trades/broker/risk/permissions/Emergency Stop-Flatten/credentials/auth/promotion/account state) | Approved Future | Fully Covered, including safety boundary | Same as row 21 | No |
| 24 | Tooltips/contextual help | Same DS-BL-027 entry; cross-refs DS-EDU-001 | Approved Future | Fully Covered | Same as row 21 | No |
| 25 | Daily/weekly review features | `DS-JRN-Journal-and-Review.md` DS-JRN-003/004 | Planned | **Now Fully Covered** — closed by the Founder Vision Completion pass (2026-07-25), paired with row 8 as anticipated | Already correct | No — resolved |
| 26 | Estimated time-in-trade | PRS §9.8: "no dedicated DS-002 requirement currently defines thesis-clock mechanics, a holding-time model, or thesis-invalidation logic"; directional only in PROJECT_SPEC.md §22, DS-PRT-004 | None | **Missing** | DS-013 backlog — should be authored (also flagged in [[DARKSAGE_FOUNDER_VISION_ALIGNMENT]] §5) | Yes |
| 27 | Ratings and explanations (grading + reasoning) | DS-SIG-001/002/003 | Committed/MVP | Fully Covered | Already correct | No |

## Cross-cutting findings

- **Both previously-flagged gaps are now closed.** Trading Journal (#8) and Daily/Weekly Review (#25) were authored together as the DS-JRN (Journal & Review Intelligence) requirement family in the 2026-07-25 Founder Vision Completion pass, exactly as this report's original recommendation anticipated — see DS-JRN-001 through DS-JRN-006.
- **One structural gap** shared with the vision-alignment report: Estimated Time-in-Trade / thesis-clock (#26) has no requirement anywhere, only a documented absence (PRS §9.8) — correctly not fabricated.
- **One scope-conflation risk**: Tax (#13) and Budgeting (#14) share a single DS-013 entry despite materially different regulatory risk and an open product-identity question ("is budgeting even in-identity for a trading-intelligence product") — recommend splitting before either is promoted.
- **One tension already flagged by the Codex itself**: Social/gamification (#11) sits at Candidate with the backlog's own note that it "leans toward Rejected pending owner review," consistent with DS-001 §9's anti-engagement-optimization stance (see [[DARKSAGE_FOUNDER_VISION_ALIGNMENT]] §13).
- No idea in this review was found to require reclassification out of its current controlled location — the gaps found are absences (nothing authored yet), not misfilings, with the single exception of the Tax/Budgeting conflation.

## Founder decisions required (summary)

1. ~~Author Trading Journal + Daily/Weekly Review as new DS-013 entries, or leave unscheduled? (#8, #25)~~ — **Resolved 2026-07-25**: authored directly as the DS-JRN DS-002 requirement family (DS-JRN-001–006) in the Founder Vision Completion pass, rather than staged through DS-013 first.
2. Split Tax Reporting from Budgeting into separate DS-013 entries? (#13, #14)
3. Is Budgeting in-identity for DarkSage at all, given DS-001 §4 defines it as trading intelligence, not personal finance? (#14)
4. Resolve Social/Gamification (#11) — Candidate or Rejected, per the backlog's own flagged tension with anti-engagement philosophy?
5. Author a GPU/local-hardware sizing requirement, or leave as an open deployment question? (#18)
6. Resolve the Business Model/Premium Tiers open question — no decision required in this pass, but flagged as unresolved. (#19)

## Revision History

| Version | Date | Change |
|---|---|---|
| 1.1.0 | 2026-07-25 | Updated rows #8 and #25 (Trading Journal, Daily/Weekly Review) from Missing to Fully Covered following the Founder Vision Completion pass's DS-JRN family; corresponding cross-cutting finding and Founder-decision item marked resolved. No other row re-evaluated in this pass. |
| 1.0.0 | 2026-07-25 | Initial founder idea coverage review at baseline `34a6581` |
