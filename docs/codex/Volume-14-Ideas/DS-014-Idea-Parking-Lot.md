# DS-014 — Idea Parking Lot

## Document Control

| Field | Value |
|---|---|
| Document ID | DS-014 |
| Title | Idea Parking Lot |
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
| 0.1.0 | 2026-07-24 | TheSinnerMan | First controlled draft, authored as part of the final grouped batch (DS-013/DS-014). Establishes the idea-parking governance model (`DS-IDG-NNN`) and a structured catalog of 25 exploratory ideas (`DS-IDEA-NNN`) — research directions, architectural inspirations, and speculative concepts not yet mature enough for DS-013. |
| 0.2.0 | 2026-07-24 | TheSinnerMan | Targeted repair for independent-audit High finding H3 (third-party model privacy/security gates). `DS-IDG-004` expanded from four gates (licensing, benchmark, compute, integration) to **nine mandatory gates**: licensing, independent benchmarking, compute requirements, privacy, security (aligned with DS-008 in full), model-supply-chain risk, untrusted-artifact/weight handling, integration-boundary risk, and operational feasibility — no third-party model candidate may be promoted until all nine are satisfied and recorded. `DS-IDEA-002` (Kronos), `DS-IDEA-019` (Training Sage as a Dedicated Model), and `DS-IDEA-020` (Distillation) updated to reference the full nine-gate requirement; Kronos remains treated strictly as a research reference, never a committed dependency. |
| 0.2.1 | 2026-07-24 | TheSinnerMan | Consolidated cleanup pass: `DS-IDEA-018` no longer cites `.ai-workflow/AGENT_PROTOCOL.md` directly as a Promotion Criteria destination or Related Feature/Volume — a public controlled document must not depend on a local-only workflow file for authority (DS-DEV-025). It now points to DS-010 process documentation or another public, committed process record instead; any local file implementing a resulting practice is explicitly described as non-authoritative operational convenience only. Appendix A Open Question #2 (DS-IDEA-018's process-vs-product classification) is unchanged and remains open. |

## 1. Purpose

DS-014 is the controlled exploratory idea repository for DarkSage. It captures speculative ideas, research directions, architectural inspirations, model references, emerging technology, and ambitious long-term concepts that are not yet mature enough to track as a potential product capability in DS-013. **All content in this document is non-committed** — no `DS-IDEA-NNN` entry carries any Release Classification (Committed/MVP, Planned, Future/Exploratory), and none becomes product direction until it is formally promoted through Codex-Driven Development (DS-001 Constitution #12): first typically into a DS-013 backlog item once it is well-defined enough, and ultimately into a dedicated DS-002+ requirement or ADR.

## 2. Scope

This document governs: the idea status taxonomy (Exploratory, Under Active Research, Promoted, Archived/Not Pursuing); the promotion path from idea to DS-013 backlog item; the treatment rule for named external models/research references (including Kronos); and the structured catalog of currently known exploratory ideas.

DS-014 does not govern: productized candidate features well-defined enough to track as a potential product capability (DS-013 — see §5's boundary rule, DS-IDG-005); committed or Planned product requirements (DS-002 through DS-009); or architecture decisions (DS-012, ADR-001–004).

## 3. Audience

Product owners, engineering/research contributors, independent auditors, and future Codex authors evaluating exploratory directions.

## 4. Definitions

See DS-001 §24 and DS-002 §4. Additional terms:

| Term | Meaning |
|---|---|
| Idea | A speculative, research-stage, or insufficiently-defined concept recorded for future consideration, carrying no product commitment of any kind |
| Research reference | A named external model, paper, technique, or project cited as architectural/research inspiration — explicitly not a dependency, requirement, or endorsement of superiority |
| Promotion (to DS-013) | The act of maturing an idea into a well-enough-defined candidate feature to be tracked as a DS-013 backlog item, per DS-013's own DS-BLG-003 promotion process for further advancement from there |

## 5. Idea Governance

### DS-IDG-001 — Non-Committed Status

**Release Classification:** Committed / MVP (governance) | **Governing Source:** DS-001 §11 (Constitution #12); DS-BLG-001 (DS-013, Committed)

**Description:** All DS-014 content is non-committed and carries no Release Classification (Committed/MVP, Planned, Future/Exploratory) until formally promoted through Codex-Driven Development into a dedicated DS-013 backlog item, DS-002+ requirement, or ADR. This mirrors DS-BLG-001's identical rule for DS-013 — DS-014 sits one level further from commitment than DS-013 does.

**Acceptance Criteria:**
- No DS-001 through DS-013 requirement or backlog item cites a `DS-IDEA-NNN` ID as its Governing Source for Committed, Planned, or Approved-Future status.
- No idea's own entry in this document states or implies a Release Classification.

**Testing:** Requirements-review check confirming no idea-only mention is treated as a committed, Planned, or Approved-Future item.

### DS-IDG-002 — Idea Status Taxonomy

**Release Classification:** Committed / MVP (governance) | **Governing Source:** DS-014 (this document, normative)

**Description:** Every idea carries exactly one Status:

- **Exploratory** — recorded for awareness and future consideration; no active work.
- **Under Active Research** — someone is actively investigating feasibility, prior art, or a preliminary technical approach.
- **Promoted** — matured into a DS-013 backlog item (cross-referenced by ID); this document retains the research-stage record as history.
- **Archived / Not Pursuing** — evaluated and explicitly set aside, with the reason recorded; retained, not deleted.

**Acceptance Criteria:** Every `DS-IDEA-NNN` item's Status field uses exactly one of these four values.

**Testing:** Status-taxonomy conformance check across all ideas on every DS-014 revision.

### DS-IDG-003 — Promotion Path to DS-013

**Release Classification:** Committed / MVP (governance) | **Governing Source:** DS-BLG-003, DS-BLG-006 (DS-013, both Committed)

**Description:** An idea matures into a DS-013 candidate only when it is understood enough to track as a potential product capability — a defined scope, a plausible Product Area, and at least a preliminary Rationale, per DS-013's own boundary rule (DS-BLG-006). At that point, a corresponding `DS-BL-NNN` entry is authored in DS-013, this idea's Status changes to Promoted, and both entries cross-reference each other by ID. The DS-014 entry is never deleted — it remains the research-stage history behind the DS-013 item.

**Acceptance Criteria:**
- No idea is marked Promoted without a corresponding, existing `DS-BL-NNN` entry in DS-013 that cross-references it.
- A promoted idea's original DS-014 entry remains in this document.

**Testing:** Promotion-record audit: every Promoted-status idea's cited `DS-BL-NNN` ID exists in DS-013 and cross-references back.

### DS-IDG-004 — Third-Party Model and Research Reference Treatment

**Release Classification:** Committed / MVP (governance) | **Governing Source:** DS-014 (this document, normative); DS-PRD-001 (DS-002, Committed, model-independence principle); DS-QA-011 (DS-009, Committed, model-evaluation non-substitution rule); DS-008 (Committed, security architecture)

**Description:** Any named external model, paper, technique, or project referenced in this document (including Kronos, §6.1) is treated strictly as an architectural or research reference: it is never a committed dependency, never assumed to be a superior model or technique without independent benchmarking, and always subject to the following mandatory review gates before any promotion beyond this document: **licensing** (terms of use, redistribution, and commercial-use rights); **independent benchmarking** (measured evaluation, per DS-QA-011, never taken on the source's own published claims alone); **compute requirements** (training/inference cost against `PROJECT_SPEC.md` §2.1's Cheap-First Architecture principle); **privacy** (what data, if any, the model was trained on or would process, and whether that exposes DarkSage user data — aligned with DS-SCA-002/003's credential/secrets handling and DS-001 §14's privacy-by-design principle); **security** (aligned with DS-008 in full — see below); **model-supply-chain risk** (provenance of the model/weights/training data, and the risk of a compromised or malicious upstream source, per DS-SCA-018's dependency-security discipline extended to model artifacts); **untrusted-artifact/weight handling** (a downloaded model file or weight checkpoint is treated as untrusted input until verified, per `SECURITY_RULES.md` "Input Validation" and DS-SCA-009's injection-defense discipline extended to binary model artifacts — never loaded or executed without integrity/provenance verification); **integration-boundary risk** (any output from a referenced model is subject to DS-PRD-011/DS-SCA-008's AI-output-validation boundary before any application use, and never gains a privileged path around the canonical `TradeValidationPipeline`, DS-EXE-001); and **operational feasibility** (maintenance, update cadence, and long-term availability of the referenced model/technique). This extends DS-PRD-001's model-independence principle (no Committed/MVP capability may hard-depend on one vendor/model without an ADR) to the research stage, and DS-QA-011's rule that model evaluation never substitutes for deterministic verification applies to any output derived from a referenced model. **No third-party model candidate may be promoted (to DS-013 or beyond) until all nine gates are satisfied and recorded** — a partial evaluation (e.g., benchmarking alone, without privacy/security/supply-chain review) is insufficient for promotion.

**Acceptance Criteria:**
- No idea entry in this document states or implies that a named external model/reference is already adopted, superior, or a dependency.
- Every idea referencing a named external model states, in its own Research Needed field, all nine mandatory gates (licensing, independent benchmarking, compute requirements, privacy, security, model-supply-chain risk, untrusted-artifact/weight handling, integration-boundary risk, operational feasibility) as preconditions for further advancement — not a subset.
- No third-party model candidate is marked Promoted (in either this document or its DS-013 cross-reference) without all nine gates recorded as satisfied.
- Security and privacy treatment for any referenced model is consistent with DS-008 in full, never a lesser or parallel security standard.

**Testing:** Content-review check across every idea naming an external model/reference, confirming all nine gates are present and consistent with this rule; security/privacy-alignment check against DS-008 (shared with DS-008's own applicable tests, e.g., DS-SCA-009's injection-defense test extended to model artifacts).

### DS-IDG-005 — Relationship to DS-013 (Boundary Rule)

**Release Classification:** Committed / MVP (governance) | **Governing Source:** DS-014 (this document, normative); DS-BLG-006 (DS-013, Committed)

**Description:** This is the DS-014-side statement of DS-013's DS-BLG-006 boundary rule: DS-014 holds the research-stage concept; DS-013 holds the productized candidate once one exists. Neither document restates the other's content as a second, independent authority — each cross-references the other by ID where a topic exists in both.

**Acceptance Criteria:** Matches DS-BLG-006's acceptance criteria exactly (shared rule, stated on both sides for document-local completeness).

**Testing:** Cross-volume duplication check between DS-013 and DS-014 (shared with DS-BLG-006's own test).

## 6. Idea Catalog

Each idea states: ID, Title, Description, Why It Is Interesting, Potential DarkSage Value, Risks/Unknowns, Research Needed, Promotion Criteria, Related Features/Volumes, Status, and Notes.

### 6.1 Market Foundation Model Research Cluster

#### DS-IDEA-001 — DarkSage Market Foundation Model

- **Description:** A large, pretrained model specialized for market/time-series data, potentially serving as a shared analytical backbone for multiple DarkSage capabilities (forecasting, regime detection, pattern recognition) rather than separate purpose-built models per task.
- **Why It Is Interesting:** Foundation-model approaches have shown strong transfer-learning results in other domains; a shared backbone could reduce duplicated modeling effort across DarkSage's analytical surfaces if it proves viable.
- **Potential DarkSage Value:** Could unify DS-IDEA-004 (Market Encoder), DS-IDEA-005 (Forecast Engine), and DS-IDEA-006 (Regime Engine) behind one trained representation, if benchmarking supports it.
- **Risks/Unknowns:** Training/maintenance cost; data requirements at foundation-model scale may exceed what a local-first, cost-conscious project can sustain (`PROJECT_SPEC.md` §2.1 Cheap-First Architecture); unproven claim until independently benchmarked against DarkSage's deterministic baselines (DS-PRD-004 boundary is never affected regardless of outcome).
- **Research Needed:** Literature review of existing market/financial foundation models; feasibility of training or fine-tuning at DarkSage's practical compute budget; benchmark design against deterministic baselines.
- **Promotion Criteria:** A concrete, benchmarked proposal with defined scope (which analytical tasks, what data, what compute) before promotion to a DS-013 backlog item.
- **Related Features/Volumes:** DS-BL-018, DS-BL-019 (DS-013, cross-referenced); DS-IDEA-002/003/004/005/006.
- **Status:** Exploratory
- **Notes:** The umbrella concept for this research cluster; DS-IDEA-002 through 006 are more specific technical directions within it.

#### DS-IDEA-002 — Market Tokenization Inspired by Kronos

- **Description:** A technique for representing market time-series data as discrete tokens (analogous to language-model tokenization), inspired by the Kronos research project's approach to financial time-series modeling.
- **Why It Is Interesting:** Tokenized time-series representations may enable applying transformer-style architectures to market data more directly than raw numerical sequences.
- **Potential DarkSage Value:** A candidate input representation for DS-IDEA-001/004 if the market-foundation-model research track advances.
- **Risks/Unknowns:** Kronos's licensing terms are not yet reviewed; its published benchmark results are not yet independently reproduced; tokenization schemes can lose information relevant to deterministic financial calculations, which must never depend on this representation (DS-PRD-004 remains absolute regardless); model weights/checkpoints obtained from an external source are untrusted artifacts until verified; unreviewed training-data provenance could carry privacy or supply-chain exposure.
- **Research Needed:** All nine of DS-IDG-004's mandatory gates — licensing (terms of use/redistribution); independent benchmarking (not taken on published claims alone); compute requirements at DarkSage's scale; privacy (training-data composition and any DarkSage-data exposure risk); security (per DS-008); model-supply-chain risk (provenance of the model/weights); untrusted-artifact/weight handling (integrity/provenance verification before any weight is loaded); integration-boundary risk (confirming no path around DS-EXE-001/DS-PRD-011); and operational feasibility (maintenance/update cadence). Also: evaluation of tokenization information loss relevant to DarkSage's own data (equities-focused, per `PROJECT_SPEC.md` §1/§5).
- **Promotion Criteria:** All nine DS-IDG-004 gates satisfied and recorded — not a subset — before any promotion to DS-013.
- **Related Features/Volumes:** DS-BL-020 (DS-013, cross-referenced); DS-IDEA-001.
- **Status:** Exploratory
- **Notes:** **Kronos is treated strictly as an architectural/research reference per DS-IDG-004 — not a committed dependency, not an assumed-superior model, and subject to licensing, independent benchmarking, compute requirements, privacy, security, model-supply-chain risk, untrusted-artifact/weight handling, integration-boundary risk, and operational feasibility evaluation.** This idea exists to track that evaluation, not to endorse adoption.

#### DS-IDEA-003 — Multi-Modal Market Representation

- **Description:** Combining multiple data modalities (price/volume time series, news text, filing documents, order-flow data) into one joint representation for analysis, rather than treating each as a separate, unrelated input.
- **Why It Is Interesting:** Markets are influenced by more than price history alone; a joint representation could surface relationships single-modality analysis misses.
- **Potential DarkSage Value:** Could inform DS-IDEA-007 (Evidence Fusion Engine) and DS-IDEA-013 (SEC filing/news/fundamental fusion) with a shared technical foundation.
- **Risks/Unknowns:** Significant architectural complexity; risk of an opaque, hard-to-explain joint representation conflicting with DS-001 §15's Explainability Standard if not carefully designed.
- **Research Needed:** Literature review of multi-modal financial modeling approaches; explainability-preserving architecture design.
- **Promotion Criteria:** A concrete architecture proposal that preserves per-modality evidence traceability (DS-PRD-002) before promotion.
- **Related Features/Volumes:** DS-BL-019 (DS-013, cross-referenced); DS-IDEA-001, DS-IDEA-007, DS-IDEA-013.
- **Status:** Exploratory
- **Notes:** None.

#### DS-IDEA-004 — Specialized Market Encoder

- **Description:** A smaller, purpose-built encoder model for extracting structured features from market data, as a lighter-weight alternative to a full foundation-model approach.
- **Why It Is Interesting:** Potentially more tractable than DS-IDEA-001 at DarkSage's compute budget while still providing specialized representation quality.
- **Potential DarkSage Value:** A near-term technical stepping stone toward DS-IDEA-001, or a standalone lighter-weight capability.
- **Risks/Unknowns:** Same evaluation burden as any specialized model (DS-BL-018's Model Benchmarking gate).
- **Research Needed:** Architecture survey; compute-cost estimate at DarkSage's scale.
- **Promotion Criteria:** Benchmarked against general-purpose provider baselines before promotion.
- **Related Features/Volumes:** DS-BL-018 (DS-013, cross-referenced); DS-IDEA-001.
- **Status:** Exploratory
- **Notes:** None.

#### DS-IDEA-005 — Forecast Engine

- **Description:** A dedicated probabilistic forecasting component producing scenario/probability distributions for price or regime outcomes, distinct from deterministic backtesting.
- **Why It Is Interesting:** Could formalize DS-IDEA-022 (Probabilistic Scenario Trees)'s output into a reusable engine.
- **Potential DarkSage Value:** Would need to integrate carefully with DS-PRD-009 (Uncertainty Communication) — any forecast output must be labeled probabilistic, never presented as deterministic fact.
- **Risks/Unknowns:** High risk of over-claiming predictive accuracy; must never be positioned as replacing DS-RSK-002's deterministic risk calculations.
- **Research Needed:** Forecasting methodology survey; calibration/backtesting-of-the-forecaster-itself methodology.
- **Promotion Criteria:** Calibration methodology proven and explicit uncertainty labeling designed before promotion.
- **Related Features/Volumes:** DS-BL-019 (DS-013, cross-referenced); DS-IDEA-001, DS-IDEA-022.
- **Status:** Exploratory
- **Notes:** None.

#### DS-IDEA-006 — Regime Engine

- **Description:** A dedicated market-regime classification component (e.g., trending/ranging/high-volatility/low-volatility), building on the MarketRegime entity (DS-DB-003) already present in DS-005's data model.
- **Why It Is Interesting:** `ROADMAP.md` Phase 3 already names "Market regime classification" directionally; this idea explores whether a specialized model improves on deterministic/statistical classification alone.
- **Potential DarkSage Value:** Could enhance DS-PERF's strategy-performance segmentation (DS-002 §5.3's Phase-3 direction) if it outperforms simpler statistical methods.
- **Risks/Unknowns:** DS-ARC-020 already requires "measured statistical evidence only — a model's guess is never a substitute for computed statistics" for Strategy Performance/DNA architecture; any Regime Engine promotion must respect this boundary exactly.
- **Research Needed:** Benchmark against the existing deterministic/statistical regime-classification approach DS-ARC-020 already anticipates.
- **Promotion Criteria:** Demonstrated improvement over statistical baseline, with the deterministic/statistical fallback always preserved as the authoritative floor (DS-ARC-020).
- **Related Features/Volumes:** DS-004 (DS-ARC-020), DS-005 (DS-DB-003); DS-IDEA-001.
- **Status:** Exploratory
- **Notes:** None.

### 6.2 Evidence, Explainability, and Uncertainty

#### DS-IDEA-007 — Evidence Fusion Engine

- **Description:** A dedicated component for combining multiple evidence sources (deterministic calculations, news, filings, Sage's own reasoning) into one coherent, traceable explanation.
- **Why It Is Interesting:** Directly serves DS-001 §15's Explainability Standard at a deeper technical level than a single Sage response alone.
- **Potential DarkSage Value:** Backing technical component for DS-BL-022 (Additional Explainability and Evidence-Fusion Systems, DS-013).
- **Risks/Unknowns:** Must preserve per-source provenance (DS-PRD-002) — a fused explanation that obscures which claim came from which source would be a regression, not an improvement.
- **Research Needed:** Fusion architecture design that preserves per-source attribution.
- **Promotion Criteria:** Architecture proposal demonstrating provenance preservation before promotion.
- **Related Features/Volumes:** DS-BL-022 (DS-013, cross-referenced); DS-IDEA-003, DS-IDEA-021.
- **Status:** Exploratory
- **Notes:** None.

#### DS-IDEA-021 — Novel Explainability Interfaces

- **Description:** UI/UX-level exploration of new ways to present explanations beyond DS-UX-009's expandable-panel pattern — e.g., interactive evidence graphs, layered drill-down visualizations.
- **Why It Is Interesting:** DS-UX-009 establishes a baseline pattern; this idea explores whether richer presentation improves comprehension without violating DS-001 §15's "shall not become a performance of certainty" constraint.
- **Potential DarkSage Value:** Could enhance both the Signal detail surface (Committed) and the future Sage conversational surface (Planned, Phase 6).
- **Risks/Unknowns:** Risk of prioritizing visual sophistication over genuine clarity, which DS-001 §8.1 (Clarity) explicitly cautions against.
- **Research Needed:** UX research on explanation comprehension; prototyping against DS-UX-009's existing pattern.
- **Promotion Criteria:** A specific interface concept validated against DS-001 §8.1/§15 before promotion to a DS-007 (DS-UX) requirement.
- **Related Features/Volumes:** DS-BL-022 (DS-013, cross-referenced); DS-007 (DS-UX-009).
- **Status:** Exploratory
- **Notes:** None.

#### DS-IDEA-022 — Probabilistic Scenario Trees

- **Description:** A visual/analytical representation of branching future scenarios with associated probabilities, rather than a single point forecast.
- **Why It Is Interesting:** Naturally communicates uncertainty (DS-PRD-009) rather than false precision, aligning with DS-001 §8's Evidence and Explainability values.
- **Potential DarkSage Value:** A candidate presentation layer for DS-IDEA-005 (Forecast Engine) output, and for DS-RSK-004's scenario analysis (Planned) once built.
- **Risks/Unknowns:** Complexity of presenting branching probability trees without overwhelming the user (tension with DS-001 §8.1 Clarity).
- **Research Needed:** UX prototyping; integration design with DS-RSK-004's deterministic scenario engine.
- **Promotion Criteria:** A specific presentation concept validated against DS-RSK-004's existing deterministic scenario-analysis requirement.
- **Related Features/Volumes:** DS-BL-022 (DS-013, cross-referenced); DS-002 (DS-RSK-004); DS-IDEA-005.
- **Status:** Exploratory
- **Notes:** None.

#### DS-IDEA-023 — Market Analog Retrieval

- **Description:** Retrieving historically similar market conditions/setups as evidence for a current analysis ("this looks like X historical period"), grounded in DS-PERF's Strategy DNA statistical infrastructure.
- **Why It Is Interesting:** Gives users a concrete, evidence-based comparison rather than an abstract probability, consistent with DS-001 §8.2 (Evidence).
- **Potential DarkSage Value:** Could extend DS-PERF-003's Strategy DNA (Planned, Phase 3) with a user-facing retrieval interface.
- **Risks/Unknowns:** Risk of implying predictive certainty from a historical analog when markets may not repeat — must be presented per DS-PRD-009's uncertainty-communication rule, and per DS-001 §13's "historical performance is not a guarantee of future performance."
- **Research Needed:** Similarity-metric design; retrieval architecture.
- **Promotion Criteria:** A similarity methodology validated as statistically meaningful (not superficial pattern-matching) before promotion.
- **Related Features/Volumes:** DS-002 (DS-PERF-003); DS-IDEA-006.
- **Status:** Exploratory
- **Notes:** None.

#### DS-IDEA-024 — Uncertainty-Aware Signal Presentation

- **Description:** Extending DS-SIG-002's deterministic signal grading with richer uncertainty presentation — e.g., confidence intervals or sensitivity ranges on the underlying scores, not just a single grade.
- **Why It Is Interesting:** Could make DS-PRD-009's uncertainty-communication principle more concrete for the Signal system specifically.
- **Potential DarkSage Value:** Enhancement to the already-Committed DS-SIG-001/002 signal-grading baseline.
- **Risks/Unknowns:** Must not alter DS-SIG-002's deterministic grading methodology itself (DS-PRD-004) — this is a presentation/uncertainty-quantification layer on top, not a replacement.
- **Research Needed:** Statistical methodology for deriving meaningful confidence bounds from the existing deterministic scoring pipeline.
- **Promotion Criteria:** A methodology that adds uncertainty quantification without altering the underlying deterministic score, validated before promotion to a DS-002 (DS-SIG) requirement.
- **Related Features/Volumes:** DS-BL-022 (DS-013, cross-referenced); DS-002 (DS-SIG-001/002).
- **Status:** Exploratory
- **Notes:** None.

### 6.3 Model Infrastructure and Orchestration

#### DS-IDEA-008 — Local Model Orchestration

- **Description:** A coordination layer for managing multiple local models (different sizes/specializations) selected per task, building on `ROADMAP.md` Phase 6's local model manager direction.
- **Why It Is Interesting:** Could improve resource efficiency by routing simple tasks to smaller models and complex tasks to larger ones.
- **Potential DarkSage Value:** Extends DS-ARC-013's AI Provider Interface (Planned, Phase 6) with a more sophisticated local-routing layer.
- **Risks/Unknowns:** Added orchestration complexity; must not compromise DS-ARC-014's zero-cloud-provider functional guarantee.
- **Research Needed:** Routing-policy design; latency/resource-tradeoff evaluation.
- **Promotion Criteria:** A routing policy proposal that preserves DS-ARC-014's zero-cloud-dependency guarantee before promotion to a DS-004 requirement.
- **Related Features/Volumes:** DS-004 (DS-ARC-013/014).
- **Status:** Exploratory
- **Notes:** None.

#### DS-IDEA-009 — Model Ensemble / Specialist-Model Architecture

- **Description:** Combining outputs from multiple specialist models (e.g., one for pattern recognition, one for regime classification) rather than relying on a single general-purpose model.
- **Why It Is Interesting:** A common technique for improving robustness over any single model; aligns with the specialist-Agent ownership pattern `AGENTS.md` already uses for human/AI contributor roles.
- **Potential DarkSage Value:** Could combine DS-IDEA-004 (Market Encoder) and DS-IDEA-006 (Regime Engine) outputs coherently.
- **Risks/Unknowns:** Ensemble disagreement handling must be explainable (DS-001 §15), not a black-box averaging step.
- **Research Needed:** Ensemble architecture design; disagreement-explanation methodology.
- **Promotion Criteria:** A specific ensemble proposal with explainable disagreement handling before promotion.
- **Related Features/Volumes:** DS-IDEA-004, DS-IDEA-006, DS-IDEA-008.
- **Status:** Exploratory
- **Notes:** None.

#### DS-IDEA-010 — Synthetic Market Generation

- **Description:** Generating synthetic (simulated, non-historical) market data for stress-testing strategies beyond available historical data.
- **Why It Is Interesting:** `ROADMAP.md` Phase 8 already names Monte Carlo simulation and risk-of-ruin analysis directionally; synthetic generation is a plausible extension technique.
- **Potential DarkSage Value:** Backing technique for DS-BL-006 (Deeper Backtesting and Synthetic Scenario Testing, DS-013).
- **Risks/Unknowns:** A statistically invalid generation method could produce misleadingly favorable backtest results — must integrate with DS-BKT-003's look-ahead-bias/data-leakage discipline and be clearly labeled as synthetic per DS-PRD-008 wherever displayed.
- **Research Needed:** Generation-methodology survey (statistical resampling, bootstrapping, or generative modeling); statistical-validity evaluation methodology.
- **Promotion Criteria:** A generation methodology with demonstrated statistical validity before promotion to a DS-002 (DS-BKT) requirement.
- **Related Features/Volumes:** DS-BL-006 (DS-013, cross-referenced); DS-002 (DS-BKT-003/004).
- **Status:** Exploratory
- **Notes:** None.

#### DS-IDEA-011 — Cross-Asset Context Modeling

- **Description:** Modeling relationships between an analyzed security and broader market/sector/macro context (e.g., correlated assets, sector rotation signals) as additional evidence.
- **Why It Is Interesting:** `ROADMAP.md` Phase 10 already names sector rotation and market breadth directionally; this idea explores a modeling approach to it.
- **Potential DarkSage Value:** Could enrich Sage's evidence base (DS-PRD-002) with cross-asset context.
- **Risks/Unknowns:** Added data-source dependency (sector/macro data feeds); must maintain per-source provenance.
- **Research Needed:** Data-source evaluation; modeling-approach survey.
- **Promotion Criteria:** A specific modeling approach and data-source plan before promotion.
- **Related Features/Volumes:** `ROADMAP.md` Phase 10; DS-IDEA-003.
- **Status:** Exploratory
- **Notes:** None.

#### DS-IDEA-012 — Options and Order-Flow Intelligence

- **Description:** Analytical use of options-market data (e.g., unusual options activity, put/call skew) and order-flow data as market-intelligence evidence, distinct from options *trading* (DS-BL-007).
- **Why It Is Interesting:** Options/order-flow data can carry information about market participants' expectations even for an equities-focused platform.
- **Potential DarkSage Value:** A market-intelligence evidence source, not necessarily requiring options trading capability itself.
- **Risks/Unknowns:** Options/order-flow data licensing is typically more expensive and specialized than equities data.
- **Research Needed:** Data-source and licensing evaluation; distinguishing this evidence-only use from DS-BL-007's options-trading scope.
- **Promotion Criteria:** Data-source licensing/cost evaluated before promotion to a DS-013 backlog item.
- **Related Features/Volumes:** DS-BL-007 (DS-013, related but distinct scope).
- **Status:** Exploratory
- **Notes:** None.

#### DS-IDEA-013 — SEC Filing, News, and Fundamental Fusion

- **Description:** Combining SEC filing data, news, and fundamental data into DarkSage's evidence base for Sage and Signal explanations.
- **Why It Is Interesting:** A concrete, well-precedented data-fusion direction (many trading-intelligence products already do this) with clear evidentiary value.
- **Potential DarkSage Value:** Directly serves DS-PRD-002's evidence-provenance principle by adding well-attributable evidence types.
- **Risks/Unknowns:** Data-source licensing (SEC filings are public, but aggregation/normalization services often are not); staleness must be disclosed per DS-PRD-008.
- **Research Needed:** Data-source and licensing evaluation.
- **Promotion Criteria:** Data-source plan and licensing evaluation complete before promotion to a DS-013 backlog item.
- **Related Features/Volumes:** DS-IDEA-003, DS-IDEA-007.
- **Status:** Exploratory
- **Notes:** None.

### 6.4 Agents, Workspace, and Coordination

#### DS-IDEA-014 — Autonomous Research Agents with Strict Boundaries

- **Description:** AI agents that autonomously conduct market research (gathering evidence, summarizing) within strictly defined, non-execution boundaries — never trading, never bypassing the deterministic core.
- **Why It Is Interesting:** Could extend Sage's research capability beyond a single conversational turn, while remaining fully within DS-003's Core Rule boundary.
- **Potential DarkSage Value:** A potential Phase-6+ Sage capability extension, strictly advisory.
- **Risks/Unknowns:** Autonomous agent behavior is inherently harder to bound and audit than single-turn interaction; must never approach DS-EXE-001's execution boundary even indirectly.
- **Research Needed:** Boundary-enforcement architecture; audit/observability requirements for autonomous multi-step agent behavior.
- **Promotion Criteria:** A boundary-enforcement design independently reviewed against DS-EXE-001/DS-SCA-012 before any promotion.
- **Related Features/Volumes:** DS-003 (Core Rule), DS-002 (DS-EXE-001), DS-008 (DS-SCA-012).
- **Status:** Exploratory
- **Notes:** High-sensitivity idea given its proximity to execution boundaries; any future work here should treat DS-EXE-001's governance boundary as non-negotiable regardless of implementation sophistication.

#### DS-IDEA-015 — Advanced Workspace Studio Concepts

- **Description:** Workspace Studio ideas beyond DS-WKS-001–006's current scope — e.g., workspace templates shared across purposes, AI-suggested layouts, context-sensitive widget recommendations.
- **Why It Is Interesting:** DS-001 §19.1's Workspace Studio Vision is intentionally broad ("may support... purpose-specific workspaces, user-selected information density, and multi-monitor workflows"), leaving room for further ideas beyond what DS-WKS/DS-UX have already captured.
- **Potential DarkSage Value:** Could inform future DS-WKS/DS-UX requirement authoring.
- **Risks/Unknowns:** Must preserve Presentation Independence (ADR-004) regardless of how sophisticated workspace suggestions become.
- **Research Needed:** UX research on workspace customization patterns in comparable products.
- **Promotion Criteria:** A specific concept well-defined enough for a DS-013 backlog item.
- **Related Features/Volumes:** DS-BL-016 (DS-013, related); DS-002 (DS-WKS), DS-007 (DS-UX-001).
- **Status:** Exploratory
- **Notes:** None.

#### DS-IDEA-016 — Future Multi-Device Coordination

- **Description:** Coordinated state/notification handoff across desktop and mobile beyond DS-ARC-003's baseline cross-client consistency — e.g., "continue on mobile" handoff, synchronized alert acknowledgment.
- **Why It Is Interesting:** A natural extension once both desktop and mobile clients exist (Phase 9+).
- **Potential DarkSage Value:** Improved cross-device UX built on the already-Committed backend-authoritative-state foundation (DS-ARC-001).
- **Risks/Unknowns:** None beyond standard multi-client synchronization complexity.
- **Research Needed:** UX research on handoff patterns.
- **Promotion Criteria:** A specific handoff concept defined once Phase 9's mobile baseline exists.
- **Related Features/Volumes:** DS-BL-015 (DS-013, related); DS-004 (DS-ARC-003).
- **Status:** Exploratory
- **Notes:** None.

#### DS-IDEA-017 — DarkSage Agent Bridge / MCP Orchestration

- **Description:** A bridge/orchestration layer allowing DarkSage's AI capabilities to interoperate with external agent/tool-orchestration protocols (e.g., Model Context Protocol-style tool interfaces), for structured tool-calling between Sage and deterministic backend services.
- **Why It Is Interesting:** Could formalize how Sage invokes deterministic tools (DS-AI-002, DS-SGE-006) using an emerging standard interface pattern rather than a bespoke one.
- **Potential DarkSage Value:** Cleaner separation between Sage's reasoning layer and the deterministic services it queries, potentially easing DS-PRD-001's model-independence goal.
- **Risks/Unknowns:** Any such bridge must still route every tool call through DS-PRD-011's AI-output-validation boundary; a generic orchestration protocol must not become a bypass path around DS-EXE-001.
- **Research Needed:** Protocol survey; security review of tool-calling boundary enforcement.
- **Promotion Criteria:** A design demonstrating the validation/execution boundaries are preserved before promotion.
- **Related Features/Volumes:** DS-003 (DS-SGE-006), DS-002 (DS-PRD-011), DS-008 (DS-SCA-008).
- **Status:** Exploratory
- **Notes:** This is a technical/architectural idea about Sage's own tool-calling infrastructure — distinct from and not to be confused with this Codex's own authoring-process tooling.

#### DS-IDEA-018 — Keeper and Development-Assistant Shared Workflow Concepts

- **Description:** Ideas for improving this Codex's own authoring/audit/governance workflow — e.g., more automated cross-reference checking, structured findings export formats.
- **Why It Is Interesting:** This Codex has now completed 14 volumes using a consistent author → self-verify → independent-audit → repair cycle; patterns worth formalizing may exist.
- **Potential DarkSage Value:** Process efficiency for future Codex authoring/maintenance, not a product capability.
- **Risks/Unknowns:** Any tooling built for this purpose is internal development process, not product functionality — must remain clearly separated from DarkSage's own public product scope (DS-DEV-024's tool-neutral public-repository requirement applies to any resulting artifacts).
- **Research Needed:** Retrospective analysis of this Codex's own authoring history for repeated patterns worth automating.
- **Promotion Criteria:** Not applicable to DS-013 product-feature promotion — this idea, if pursued, would inform DS-010 process documentation or another public, committed process record, not a product requirement. Any local, non-committed workflow file that happens to implement a resulting practice does so only as operational convenience and is never cited here as this idea's authority or destination (DS-DEV-025's local-workflow-authority rule).
- **Related Features/Volumes:** DS-010 (development standards).
- **Status:** Exploratory
- **Notes:** This idea concerns DarkSage's own engineering process, not a DarkSage product feature — it is recorded here for completeness per the batch instruction but would never itself become a DS-002+ requirement; at most it could inform a future DS-010 revision.

### 6.5 Sage Model Training and Specialization

#### DS-IDEA-019 — Training Sage as a Dedicated Local/Open-Weight Model

- **Description:** Training or fine-tuning a dedicated open-weight model specifically for Sage's role, rather than relying solely on general-purpose local/cloud providers.
- **Why It Is Interesting:** Could improve Sage's domain fluency and reduce dependency on any single external provider, advancing DS-PRD-001's model-independence goal further.
- **Potential DarkSage Value:** A deeper investment in local-first AI (DS-ARC-014) beyond the general-purpose provider-abstraction baseline.
- **Risks/Unknowns:** Training cost and expertise requirements are substantial; base open-weight model licensing must be reviewed; base model weights are untrusted artifacts until provenance/integrity is verified; training-data composition of the base model may carry privacy or supply-chain exposure not yet assessed.
- **Research Needed:** All nine of DS-IDG-004's mandatory gates (licensing, independent benchmarking, compute requirements, privacy, security per DS-008, model-supply-chain risk, untrusted-artifact/weight handling, integration-boundary risk, operational feasibility) applied to each candidate base model, plus training/fine-tuning cost estimate.
- **Promotion Criteria:** A specific base model with all nine DS-IDG-004 gates satisfied and recorded, and a training plan benchmarked against general-purpose providers, before promotion.
- **Related Features/Volumes:** DS-BL-018 (DS-013, cross-referenced); DS-IDEA-001, DS-IDEA-020.
- **Status:** Exploratory
- **Notes:** Any candidate base/open-weight model is a third-party model candidate under DS-IDG-004 and subject to its full nine-gate review before promotion.

#### DS-IDEA-020 — Distillation and Adapter-Based Specialization

- **Description:** Using knowledge distillation or lightweight adapter techniques (e.g., LoRA-style) to specialize a smaller local model from a larger reference model's behavior, as a lower-cost alternative to full training (DS-IDEA-019).
- **Why It Is Interesting:** Adapter-based approaches are typically far cheaper than full fine-tuning while still providing meaningful specialization.
- **Potential DarkSage Value:** A more tractable near-term path toward DS-BL-018/021's specialized-model goals than full training.
- **Risks/Unknowns:** Distillation from a licensed reference model may carry redistribution restrictions; the reference model's weights are an untrusted artifact until verified; requires the same full review as any other referenced model (DS-IDG-004), not licensing alone.
- **Research Needed:** Technique survey; all nine of DS-IDG-004's mandatory gates applied to each candidate reference/base model.
- **Promotion Criteria:** A specific technique and target model pair, with all nine DS-IDG-004 gates satisfied and recorded, before promotion.
- **Related Features/Volumes:** DS-BL-018, DS-BL-021 (DS-013, cross-referenced); DS-IDEA-002, DS-IDEA-019.
- **Status:** Exploratory
- **Notes:** Any candidate reference/base model for distillation is a third-party model candidate under DS-IDG-004 and subject to its full nine-gate review before promotion.

### 6.6 Broader Research Direction

#### DS-IDEA-025 — Future Research into Additional Open Financial Models

- **Description:** An ongoing, general-purpose research watch for newly published open-weight or open-research financial/market models beyond Kronos (DS-IDEA-002), to be evaluated as they emerge.
- **Why It Is Interesting:** The open financial-modeling research landscape is active and evolving; a standing watch avoids anchoring exclusively on any one reference.
- **Potential DarkSage Value:** Keeps DS-IDEA-001's foundation-model research track informed by the broader field rather than a single reference point.
- **Risks/Unknowns:** None specific — this is a research-monitoring practice, not a technical commitment.
- **Research Needed:** Ongoing literature/release monitoring; no fixed endpoint.
- **Promotion Criteria:** A specific newly-identified model is promoted into its own dedicated `DS-IDEA-NNN` entry (following DS-IDG-004's treatment rule) once it merits individual tracking, rather than being folded into this general entry indefinitely.
- **Related Features/Volumes:** DS-IDEA-001, DS-IDEA-002.
- **Status:** Under Active Research
- **Notes:** This entry is intentionally open-ended; per DS-IDG-004, any specific model surfaced through this research is treated with the same non-dependency, non-superiority, evaluation-required discipline as Kronos.

## 7. Non-Goals

DS-014 does not: commit any idea to Committed, Planned, or Approved-Future status by virtue of inclusion (DS-IDG-001); assume any named external model or research reference is superior, adopted, or a dependency without independent benchmarking and licensing review (DS-IDG-004); duplicate DS-013's productized-candidate content as a second, competing description (DS-IDG-005 — cross-reference instead); or commit to a specific AI/ML architecture, training approach, or vendor.

## 8. Dependencies

- [DS-001](../Volume-01-Foundation/DS-001-Executive-Vision.md), [DS-002](../Volume-02-Product/DS-002-SRS.md), [DS-003](../Volume-03-Sage/DS-003-Sage-AI-Bible.md), [DS-004](../Volume-04-Architecture/DS-004-Technical-Architecture.md), [DS-009](../Volume-09-Testing/DS-009-Testing-and-QA.md)
- [DS-013](../Volume-13-Backlog/DS-013-Feature-Backlog.md) (this batch, cross-referenced items)
- `ROADMAP.md`, `PROJECT_SPEC.md`

## 9. Risks and Constraints

- **Classification discipline:** no idea carries a Release Classification; every idea explicitly states Research Needed and Promotion Criteria rather than implying current direction.
- **Third-party model discipline:** every idea naming an external model/reference (DS-IDEA-002, and any future entries under DS-IDEA-025's ongoing watch) explicitly carries DS-IDG-004's non-dependency, non-superiority, evaluation-required treatment — preventing this document from becoming an implicit roadmap toward any specific external technology.
- **Process-vs-product boundary:** DS-IDEA-018 (Codex workflow concepts) is explicitly flagged as concerning DarkSage's own engineering process rather than a product feature, to prevent it from being mistaken for a product-backlog candidate.

## 10. Verification Approach

Document-level verification (unique-ID check across `DS-IDG-NNN`/`DS-IDEA-NNN`, cross-reference consistency against DS-001 through DS-004/DS-009/DS-013, no idea carrying an implied Release Classification, DS-013 cross-references valid, Kronos and all other named models treated per DS-IDG-004) recorded in `.ai-workflow/HANDOFF.md`.

## 11. References

- `ROADMAP.md`, `PROJECT_SPEC.md`
- `docs/codex/Volume-01-Foundation/DS-001-Executive-Vision.md`
- `docs/codex/Volume-03-Sage/DS-003-Sage-AI-Bible.md`
- `docs/codex/Volume-09-Testing/DS-009-Testing-and-QA.md`
- `docs/codex/Volume-13-Backlog/DS-013-Feature-Backlog.md`

## Appendix A — Open Questions

1. **Kronos and market-foundation-model licensing/benchmarking** — entirely unresolved; DS-IDEA-002 exists specifically to track this evaluation, not to presuppose its outcome.
2. **DS-IDEA-018's process-vs-product classification** — recorded as a genuine boundary question: this Codex has no precedent for whether an internal-process idea belongs in DS-014 at all; retained here per the batch instruction, flagged for future governance clarification.
3. **Governance-confirmation carryover** — the standing `BLOCKERS.md` items apply identically here and are not re-litigated.
