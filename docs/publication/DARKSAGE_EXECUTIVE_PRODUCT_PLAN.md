# DSF-004 — DarkSage Executive Product Plan

## 1. Document Control

| Field | Value |
|---|---|
| Document ID | DSF-004 |
| Title | DarkSage Executive Product Plan |
| Version | 0.1.0 |
| Status | Draft |
| Owner | Keeper (delegated authority) |
| Contributors | |
| Classification | Internal |
| Repository | LightSwornPVP/DarkSage |
| Created | 2026-07-25 |
| Last Updated | 2026-07-25 |
| Source Baseline Commit | e2f73a7ade28ce97caad1eb2e06d43ef0ac0aed8 (docs: add DarkSage publication architecture and PRS) — verified against `git rev-parse HEAD` |
| Controlling Sources | DS-001 (vision, philosophy, principles); DS-011 (roadmap); [DSF-002](../requirements/DARKSAGE_PRODUCT_REQUIREMENTS_SPECIFICATION.md) (consolidated requirements); [DSF-001](DARKSAGE_PUBLICATION_ARCHITECTURE.md) §B.1 (this family's role, audience, authority, and length target) |
| Authority Boundary | Per DSF-001 §B.1: **zero independent requirement authority.** Every factual or normative claim in this document traces to DS-001, DS-011, or DSF-002. This document does not replace the PRS or the Codex; a reader needing the actual product contract is directed to DSF-002. It creates no `DS-<DOMAIN>-NNN` requirement, no Release Classification, and no implementation commitment of its own. |
| Publication Relationship | Subordinate to [DSF-001](DARKSAGE_PUBLICATION_ARCHITECTURE.md) §A's three-tier publication authority hierarchy and to [DSF-003](DARKSAGE_VISUAL_DESIGN_SYSTEM.md) for visual treatment. Uses the templates in `docs/publication/templates/` and figures from `docs/publication/DIAGRAM_REGISTER.md`. |

Status lifecycle: Draft → Under Review → Approved → Superseded/Deprecated.

### Document ID Rationale

`DSF-004` is the next unused identifier in the `DSF-NNN` namespace (`docs/standards/NAMING_AND_ID_STANDARD.md` §Flagship Publication Documents), following `DSF-001` (Publication Architecture), `DSF-002` (Product Requirements Specification), and `DSF-003` (Visual Design System). The naming standard already names "an Executive Product Plan" as an explicit example of the namespace's intended use; no standards change was required to assign this ID.

## Revision History

| Version | Date | Author | Summary |
|---|---|---|---|
| 0.1.0 | 2026-07-25 | Keeper (delegated authority) | First controlled draft. Independent-audit HIGH1 repair: authored the DarkSage Executive Product Plan named but not yet authored by DSF-001 §B.1/§J. Twenty required sections, target 25–45 polished pages, zero independent requirement authority — every normative claim traces to DS-001, DS-011, or DSF-002. Figure placeholders reference `docs/publication/DIAGRAM_REGISTER.md` Figures 1, 5, 6, 11, 12, and 17 by exact ID. No DS-001 through DS-014 volume, ADR, DSF-001, DSF-002, or DSF-003 content was changed to produce this document. |

## Non-Goals

This document does not: create a `DS-<DOMAIN>-NNN` product requirement; state a Release Classification, implementation commitment, or numeric target not already stated in DS-001, DS-011, or DSF-002; claim any capability, integration, or platform exists where the controlling sources say it is Planned or Future/Exploratory; promise profit, prediction accuracy, or freedom from loss; frame DarkSage as an autonomous "AI trader"; or generate a DOCX/PDF artifact.

---

## 2. Cover Content

**DarkSage**
Executive Product Plan
Version 0.1.0 — Draft
Owner: Keeper (delegated authority) | Classification: Internal

> Wisdom Over Noise

*Source repository: LightSwornPVP/DarkSage. Source baseline commit: `e2f73a7`. Generation date: not yet generated (Markdown draft only). Publication version: not yet assigned — no DOCX/PDF exists for this document.*

## 3. Executive Summary

DarkSage is a trading intelligence and decision-support platform (DS-001 §4). Its purpose is to help people investigate markets, test ideas, understand risk, and make better-informed decisions through evidence and explanation — not to predict outcomes, guarantee returns, or replace the user's judgment with automated authority.

This plan is a **derived, non-authoritative narrative summary**. It exists so a partner, prospective contributor, or non-specialist reviewer can understand what DarkSage is, why it exists, how it is meant to feel to use, and how its safety model works — without reading all fourteen Codex volumes. Every claim in this document traces back to an approved source (DS-001, DS-011, or [DSF-002](../requirements/DARKSAGE_PRODUCT_REQUIREMENTS_SPECIFICATION.md)); where this plan and a controlling source differ, the controlling source governs and this plan is a defect to be corrected (DSF-001 §A.2.4).

DarkSage is built around a small number of durable ideas: evidence over hype, visible risk, deterministic financial truth, and a strict separation between an AI assistant that advises and a Risk Engine that alone decides what is safe to execute. Sage — DarkSage's AI-assistance layer — never gains execution authority. No trade is ever a mandatory answer: Sage, the Scanner, and the Strategy Lab are all permitted, and expected, to conclude that the right action is no action.

## 4. The Problem

Markets produce more information than any person can continuously absorb. More information does not automatically create better decisions — without context, evidence, and disciplined risk awareness, it often creates noise (DS-001 §1 Foreword). DS-001 §5 identifies five enduring problems DarkSage is built to address:

1. **Information overload** — relevant evidence is difficult to separate from distraction.
2. **Fragmentation** — research, testing, risk, portfolio context, and education are often disconnected across separate tools.
3. **Opaque conclusions** — users may receive scores or signals without sufficient reasoning or stated limitations.
4. **Hidden or underweighted risk** — opportunity is emphasized while downside, uncertainty, and invalidation are obscured.
5. **Loss of user authority** — automation and AI can silently become decision-makers rather than tools.

DarkSage's premise is that solving these problems does not require promising certainty markets cannot provide — it requires better structure, better explanation, and a design that keeps the user in charge.

## 5. The DarkSage Answer

DarkSage's vision (DS-001 §6) is a transparent, explainable, and customizable trading intelligence platform that helps people transform market information into understanding and disciplined decisions. It aims to make sophisticated analysis approachable without making it shallow, and advanced capability powerful without making it needlessly obscure.

DarkSage is not merely a stock screener, charting application, chatbot, backtester, portfolio tracker, or autonomous trading bot (DS-001 §4) — those categories describe possible capabilities the platform unifies over time, not the product as a whole. That unification spans market intelligence, scanning and discovery, charting and analysis, strategy research and backtesting, portfolio and risk intelligence, explainable AI assistance through Sage, customizable workspaces, and trading knowledge and education. This is a product direction, not a commitment to every individual feature shipping on a fixed date (DS-001 §4).

## 6. Core Principles

DS-001 §11's DarkSage Constitution states thirteen principles intended to remain durable across product versions. The seven most load-bearing for a reader new to the product:

| Principle | What it means in practice |
|---|---|
| **User Authority** | Consequential decisions remain under explicit user authority — DarkSage proposes and explains; it does not decide for the user. |
| **Wisdom Over Noise** | Information is valuable only when transformed into relevant understanding — DarkSage's brand motto and product filter. |
| **Evidence Before Hype** | Claims are proportionate to their evidence; inference is never presented as fact (DS-001 §8.2). |
| **Visible Risk** | Material downside and uncertainty are never concealed to make an opportunity look more attractive (DS-001 §8.4). |
| **Deterministic Financial Truth** | Material financial calculations come from deterministic implementations — never from generative model output (DS-001 §11.6, ADR-003). |
| **Sage Advises; the User Decides** | Sage supports judgment and never becomes an unquestionable authority (DS-001 §11.7, ADR-002). |
| **No Silent Capability Changes** | Authority, integrations, permissions, data access, and enabled capabilities change only through explicit action (DS-001 §11.10). |

The full thirteen-item Constitution, and the eight Core Values underlying it (Clarity, Evidence, User Authority, Visible Risk, Explainability, Privacy and Security, Restraint — DS-001 §8), are stated verbatim in DS-001 §8/§11 and are not restated in full here to avoid a second, drifting copy.

## 7. Product Experience

DarkSage should demonstrate clarity before clutter, progressive disclosure, fast access to important information, customization without chaos, consistent terminology, visible data freshness and provenance, meaningful and safe defaults, graceful degradation, understandable errors, and power without unnecessary complexity (DS-001 §19).

**Figure 1 — DarkSage Product Ecosystem** *(placeholder; see `docs/publication/DIAGRAM_REGISTER.md` row 1 — status: Not Yet Authored)*. Shows how market data, Scanner, Signals, Charts, Strategy, Portfolio, Sage, and Auto-Trader relate as one platform, as a set of connected capability areas around a shared backend, without implying any capability not yet Committed/Planned.

DarkSage may present two compatible vocabularies (DS-001 §17): themed, Codex-inspired terminology that gives the product character (Observatory, Watchtower, Forge, Chronicle, Guardian, Treasury) alongside plain professional terminology (Market Data/Market Intelligence, Scanner, Strategy Builder/Strategy Lab, Backtesting/Historical Analysis, Risk Engine, Portfolio). These mappings are illustrative examples, not final UI-label requirements — users are never forced to learn themed terminology to use professional financial tooling, and character never reduces clarity, accessibility, or precision.

**Workspace Studio** (Current Product Direction, DS-001 §19.1) is the high-level vision for customizable dashboards — drag-and-drop layout, resizable components, saved layouts, purpose-specific workspaces — coexisting with beginner-friendly defaults. This is a directional vision, not a UI framework, persistence format, or layout implementation commitment.

## 8. How DarkSage Thinks

DarkSage should prefer understanding over unexplained output, honest uncertainty over false precision, and it distinguishes observation, calculation, inference, and recommendation as four different things (DS-001 §9). It uses deterministic computation when the problem is deterministic, and AI where reasoning, synthesis, explanation, personalization, or natural-language interaction creates meaningful value — never merely because AI can be used.

**Figure 6 — Deterministic-versus-AI Responsibility Split** *(placeholder; see `docs/publication/DIAGRAM_REGISTER.md` row 6 — status: Not Yet Authored)*. Shows which calculations are deterministic-only (risk, backtests, indicators, portfolio math) versus where AI may contribute (explanation, synthesis, tutoring); deterministic items never accept generative model output as their authoritative value.

Recommendations are decision support, not commands. Automation is explicit, bounded, observable, and controlled by the user within approved safety systems (DS-001 §9). When relevant to a material conclusion, DarkSage's Explainability Standard (DS-001 §15) helps a user answer: why this conclusion, what evidence supports it, how strong and current that evidence is, what uncertainty exists, what material risks are present, which assumptions matter, and what would invalidate the conclusion.

## 9. Illustrative Trade Assessment

> **ILLUSTRATIVE EXAMPLE — NOT LIVE DATA.** Every value below is a hypothetical placeholder chosen for narrative clarity. No ticker, price, indicator reading, or outcome shown here reflects real market data, a real DarkSage output, or an implemented feature — this section illustrates the *shape* of an assessment, not a promised result.

A user reviews a hypothetical Scanner result for illustrative-ticker `EXMPL`. DarkSage would surface: the evidence considered (illustrative price/volume/indicator context), the confidence and its basis, material risks and invalidation conditions, and — critically — an explicit statement that **"No Trade" is always a valid, correctly-scored outcome**, not a failure state. A strategy or Sage assessment that concludes the disciplined action is to do nothing is functioning exactly as intended (DS-001 §9, "support thoughtful action, including the decision not to act").

If Sage is asked to comment on the illustrative assessment, its response would explain reasoning and surface risk — it would never place, schedule, or queue an order. Any move toward an actual trade would still pass through the full [canonical `TradeValidationPipeline`](#11-safety-by-design) regardless of what Sage or the Scanner concluded.

## 10. Sage

**Sage advises. The user decides.** (DS-001 §12, ADR-002.) Sage is DarkSage's intelligence and AI-assistance layer. It should explain reasoning, identify supporting evidence, communicate uncertainty, surface meaningful risks, and describe what could invalidate a conclusion — it should assist rather than replace judgment.

**Figure 5 — Sage Advisory Boundary** *(placeholder; see `docs/publication/DIAGRAM_REGISTER.md` row 5 — status: Authored, source at `docs/publication/diagrams/source/figure-05-sage-advisory-boundary.mmd`, not yet rendered)*. States explicitly that no arrow exists from Sage directly to the Execution Engine or Broker Adapter under any circumstance.

Sage shall (DS-001 §12): distinguish evidence from inference; avoid unsupported certainty; avoid fabricating deterministic financial results; respect explicit user authority; never silently escalate from advice to execution authority; and never bypass or silently override the Risk Engine. Per [DSF-002](../requirements/DARKSAGE_PRODUCT_REQUIREMENTS_SPECIFICATION.md) §9.15, the requirements that hold this boundary in place — Model Independence, Evidence Provenance, Presentation Independence, Deterministic Financial Truth, User Decision Authority, Risk Engine Authority, No Unapproved Autonomous Trading, Data State Visibility, Uncertainty Communication, AI Output Validation — are **Committed/MVP regardless of Sage's own broader Planned/Phase-6 classification.**

DarkSage is not framed as an "AI trader." Sage is an assistant with a fixed, structural boundary against execution authority — that boundary is not a configurable setting.

## 11. Safety by Design

DarkSage's safety model rests on one canonical, twelve-stage pipeline that every trade-shaped action passes through, reproduced here exactly (per `docs/pipeline-stages.txt`, no renaming, reordering, or omission permitted):

```
AI / Strategy Engine
Trade Proposal
Signal Validator
Strategy Validation
Risk Engine
Permissions Engine
Portfolio / Exposure Checks
Buying Power Checks
Market Condition Checks
Order Validation
Execution Engine
Broker Adapter
```

AI may only originate a Trade Proposal (the first two stages); every subsequent stage is deterministic, independently-authoritative validation, permission, or execution logic that AI cannot bypass, skip, or silently override.

**Figure 12 — Emergency Stop versus Emergency Flatten** *(placeholder; see `docs/publication/DIAGRAM_REGISTER.md` row 12 — status: Not Yet Authored)*. Contrasts the two controls' exact scope (block-new-orders-only vs. also-closes-positions) and authentication requirement.

Additional standing safety rules (DS-001 §13, [DSF-002](../requirements/DARKSAGE_PRODUCT_REQUIREMENTS_SPECIFICATION.md) §11): material risk remains visible and is never hidden to make an opportunity look more attractive; Sage cannot bypass or silently override the Risk Engine; historical performance and backtest results are never presented as guaranteed future outcomes; **paper trading is the mandatory starting point** for any strategy on its way toward live execution; **limited live and full live trading remain future-gated** behind the Live Trading Gate below; and **no development agent, background process, or automated tooling may enable live trading — only an explicit, authenticated user action can.**

## 12. Architecture Overview

DarkSage's backend is the sole authority over trading and account state. Desktop and (Planned, Phase 9) mobile clients read and display backend-computed state; neither independently computes or stores authoritative trading state, and neither is a peer of the backend (DS-ARC-001, `ARCHITECTURE.md` §2). Market-data, broker, and AI provider integrations sit behind a common adapter interface, so consuming code depends on the interface, not on any named vendor (DS-ARC-006, DS-ARC-013). Every downstream data value carries its provenance and freshness state — current, delayed, stale, historical, or simulated — from ingestion through to display (`ARCHITECTURE.md` §7).

This section is a high-level orientation only; the authoritative technical architecture is DS-004, and this plan creates no architecture decision or requirement of its own.

## 13. Research and Intelligence

DarkSage's research surface spans market data and provenance, Scanner and watchlists, Signals with an explained lifecycle, charting and indicators, pattern recognition, and portfolio intelligence ([DSF-002](../requirements/DARKSAGE_PRODUCT_REQUIREMENTS_SPECIFICATION.md) §9.1–9.7, §9.13). A Trading Knowledge Engine or equivalent educational intelligence may organize contextual terminology, indicator, and strategy education, supporting evidence-based learning rather than unquestionable doctrine (DS-001 §19.2).

Some research directions frequently associated with "alternative data" platforms are explicitly **not** committed capabilities: political/legislative-trading intelligence (SEC/Congress disclosures), insider-transaction feeds, institutional-holdings intelligence, macro overlays, and other alternative-data sources are **Non-Committed Research References** in DS-013/DS-014 with no current Codex requirement grounding, several requiring legal review before any promotion ([DSF-002](../requirements/DARKSAGE_PRODUCT_REQUIREMENTS_SPECIFICATION.md) §9.9). This plan states that boundary plainly rather than implying these capabilities already exist.

## 14. Why DarkSage Is Different

Most tools in this space pick one lane: a screener finds candidates but doesn't explain risk; a chatbot explains but can't calculate deterministically; a backtester proves a strategy historically but leaves live discipline to the user; an autonomous bot removes the user from the loop entirely. DarkSage's differentiation is structural, not cosmetic:

- **Evidence-first, not signal-first.** Conclusions carry their supporting evidence, uncertainty, and invalidation conditions, not just a score (DS-001 §15).
- **A hard, structural line between advice and execution.** Sage can explain and synthesize; only the deterministic pipeline (§11 above) can move a proposal toward an order.
- **Presentation Independence.** Hiding or moving a workspace widget never disables an underlying enabled capability, and never changes analytical behavior (DS-001 §16, ADR-004).
- **Paper-first by construction**, not by policy alone — the Gate-chain (§15) makes live trading a later, explicitly-gated phase, not a toggle.
- **No false certainty.** DarkSage would rather say "no trade" or "uncertain" than manufacture confidence (§9 above).

## 15. Roadmap

DarkSage's fifteen `ROADMAP.md` phases (0–14) are categorized by DS-RM-015 into Strict, Parallel, Optional/Deferred, and Gate-chain sequencing. Phase inclusion alone never promotes a deliverable to Committed or Planned (DS-RM-012) — this plan states each phase's category exactly as DS-011 §6 does, without upgrading any of them.

**Figure 17 — Phase 0–14 Roadmap** *(placeholder; see `docs/publication/DIAGRAM_REGISTER.md` row 17 — status: Authored, source at `docs/publication/diagrams/source/figure-17-phase-roadmap.mmd`, not yet rendered)*.

The **Gate-chain** — the strict paper-first/live-later sequence — is the backbone of DarkSage's path to real money:

**Figure 11 — Paper-to-Live Promotion Path** *(placeholder; see `docs/publication/DIAGRAM_REGISTER.md` row 11 — status: Authored, source at `docs/publication/diagrams/source/figure-11-paper-to-live-promotion-path.mmd`, not yet rendered)*.

Phase 7 (Paper Auto-Trader) → Phase 8 (Shadow Trading and Strategy Tournament) → Phase 12 (Production Hardening) → Phase 13 (Limited Live Trading) → Phase 14 (Full Live Platform). Entry into Phase 13 — the first phase where any real money moves — requires every one of the eight DS-EXE-007 Live Trading Gate prerequisites: acceptable paper performance, an independent security review passed, broker reconciliation passed, the kill switch (Emergency Stop/Flatten) tested and passed, data-health checks passed, duplicate-order prevention passed, active monitoring, and the user having explicitly and separately unlocked live trading. **No development agent or AI process may satisfy this gate.**

Phases 9 (Mobile), 10 (Advanced Research), and 11 (Options Research) are Parallel/Optional tracks — they do not gate, and are not gated by, the Gate-chain.

`ROADMAP.md` Phase 7's deliverable list mentions a "trade journal." Consistent with [DSF-002](../requirements/DARKSAGE_PRODUCT_REQUIREMENTS_SPECIFICATION.md) §9.14, this plan preserves Journal as **non-committed roadmap direction without dedicated requirement or DS-013 backlog authority** — a conceptual/directional area, neither approved nor rejected, pending its own dedicated requirement authoring. No journal/behavioral-review acceptance criteria are invented here.

## 16. Definition of Success

DarkSage's mission (DS-001 §7) is to organize market evidence into usable context, help users explore and test ideas, make material risk and uncertainty visible, explain analytical conclusions and their limitations, support growth in market understanding, and preserve user authority over consequential decisions.

Consistent with that mission, this plan defines success as **clarity and disciplined decision-making, not investment outcomes**: a user who understands why DarkSage reached a conclusion, who can see the risk plainly, who is never surprised by a silent capability or authority change, and who remains in control of every consequential decision. DarkSage does not define success as, and this document makes no claim toward, guaranteed returns, prediction accuracy, or trading profitability — DS-001 §10's User Promise explicitly states these promises constrain product design; they do not promise profit, prediction accuracy, or freedom from loss.

## 17. Flagship Documentation

This plan is one of three flagship publication document families (DSF-001 §B): the **Executive Product Plan** (this document, narrative introduction), the **[DarkSage Product Requirements Specification](../requirements/DARKSAGE_PRODUCT_REQUIREMENTS_SPECIFICATION.md)** (DSF-002, the practical build contract), and the **DarkSage Codex — Complete Edition** (the full fourteen-volume DS-001–DS-014 suite, packaged with indexes and cross-references, content unchanged). All three derive from the same approved Markdown source; none is authoritative over another; the Markdown source governs all three (DSF-001 §B, Diagram Register Figure 19).

A reader who needs the actual, complete product contract — every requirement ID, acceptance criterion, and classification — should go to DSF-002, not this plan.

## 18. Disclaimers

This document is provided for informational and product-planning purposes. It does not constitute financial, investment, or trading advice, and makes no guarantee of profit, prediction accuracy, or freedom from loss (DS-001 §21, DSF-002 §9). DarkSage is not a promise of profit, a guaranteed market predictor, a substitute for user judgment, an opaque autonomous trader, a system where AI output is unquestionable truth, or a system that hides risk to make recommendations attractive (DS-001 §21).

No DS-001 through DS-014 volume, ADR, or `ROADMAP.md` phase establishes a six-user (or any specific user-count) private-deployment requirement or commitment; where such a deployment is discussed elsewhere, it is external deployment discussion, not a product-governance commitment, and this document does not treat it as a controlled scope item ([DSF-002](../requirements/DARKSAGE_PRODUCT_REQUIREMENTS_SPECIFICATION.md) §20).

This plan itself creates no requirement, classification, or architecture authority — see the Document Control's Authority Boundary above.

## 19. References

- [DS-001 — Executive Vision & Product Foundation](../codex/Volume-01-Foundation/DS-001-Executive-Vision.md)
- [DS-011 — Development Roadmap](../codex/Volume-11-Roadmap/DS-011-Development-Roadmap.md) *(exact filename per `docs/CODEX_INDEX.md`)*
- [DSF-001 — DarkSage Publication Architecture](DARKSAGE_PUBLICATION_ARCHITECTURE.md)
- [DSF-002 — DarkSage Product Requirements Specification](../requirements/DARKSAGE_PRODUCT_REQUIREMENTS_SPECIFICATION.md)
- [DSF-003 — DarkSage Visual Design System](DARKSAGE_VISUAL_DESIGN_SYSTEM.md)
- `docs/publication/DIAGRAM_REGISTER.md`
- `docs/pipeline-stages.txt`
- `ROADMAP.md`

## 20. Revision History

See the Document Control section's Revision History table above (this document's single-table convention follows DSF-003's precedent rather than duplicating the table at both the top and bottom of the document).
