# DS-001 — Executive Vision & Product Foundation

## Document Control

| Field | Value |
|---|---|
| Document ID | DS-001 |
| Title | Executive Vision & Product Foundation |
| Version | 1.0.0 |
| Status | Approved |
| Project | DarkSage |
| Owner | TheSinnerMan |
| Contributors | |
| Classification | Internal |
| Repository | LightSwornPVP/DarkSage |
| Created | 2026-07-23 |
| Last Updated | 2026-07-23 |

Status lifecycle: Draft → Under Review → Approved → Superseded/Deprecated.

## Revision History

| Version | Date | Author | Summary |
|---|---|---|---|
| 0.2.0 | 2026-07-23 | TheSinnerMan | First substantial controlled draft of the executive vision and product foundation. |
| 0.9.0 | 2026-07-23 | TheSinnerMan | Owner-review refinement; terminology normalization; normative-language refinement; promoted to Under Review. |
| 1.0.0 | 2026-07-23 | TheSinnerMan | Approved initial release of DS-001 following owner review. |

## 1. Foreword

DarkSage begins with a simple belief: technology should help people think more clearly, not think for them.

Markets produce more information than any person can continuously absorb. More information does not automatically create better decisions; without context, evidence, and disciplined risk awareness, it often creates noise. DarkSage exists to turn that noise into structured understanding while preserving the user's authority.

> **Wisdom Over Noise**

This document establishes the durable product principles that future DarkSage requirements, design decisions, user experiences, security controls, analytical systems, and implementation work shall respect.

## 2. Purpose

DS-001 defines why DarkSage exists, what kind of product it is, whom it serves, and the principles that govern its evolution.

It is the highest-level product and philosophical authority within the DarkSage Codex. It guides lower-level specifications without replacing them. When a proposed feature or design conflicts with this foundation, that conflict shall be resolved explicitly rather than hidden in implementation detail.

## 3. Scope

This document governs:

- product identity and purpose;
- user authority and the role of automation;
- Sage's product-level role and boundaries;
- treatment of evidence, uncertainty, explainability, and risk;
- deterministic financial truth;
- privacy, security, and presentation principles;
- target users and intended product experience;
- platform direction, non-goals, and long-term aspirations; and
- the relationship between DS-001 and the rest of the DarkSage Codex.

Detailed functional requirements belong in DS-002. Detailed Sage behavior belongs in DS-003. Detailed technical architecture belongs in DS-004. Data, API, UI/UX, security, testing, development, and roadmap details belong in their respective Codex volumes.

## 4. Product Definition

**FOUNDATIONAL PRINCIPLE**

DarkSage is a trading intelligence and decision-support platform. Its purpose is to help users investigate markets, test ideas, understand risk, and make better-informed decisions through evidence and explanation.

DarkSage is not merely a stock screener, charting application, chatbot, backtester, portfolio tracker, or autonomous trading bot. Those categories describe possible capabilities, not the product as a whole.

Over time, DarkSage is intended to unify:

- market intelligence and market data;
- scanning and discovery;
- charting and analysis;
- strategy research and backtesting;
- portfolio and risk intelligence;
- explainable AI assistance through Sage;
- customizable workspaces;
- trading knowledge and education; and
- decision support.

This definition establishes product direction, not a detailed commitment to individual features.

## 5. Problem Statement

Market participants face fragmented tools, inconsistent data, opaque signals, excessive information, and systems that often emphasize activity over understanding. Beginners may be overwhelmed by unexplained terminology, while experienced users may be constrained by simplistic workflows or closed analytical assumptions.

DarkSage seeks to address five enduring problems:

1. **Information overload:** relevant evidence is difficult to separate from distraction.
2. **Fragmentation:** research, testing, risk, portfolio context, and education are often disconnected.
3. **Opaque conclusions:** users may receive scores or signals without sufficient reasoning or limitations.
4. **Hidden or underweighted risk:** opportunity can be emphasized while downside, uncertainty, and invalidation are obscured.
5. **Loss of user authority:** automation and AI can silently become decision-makers rather than tools.

DarkSage should reduce these problems without creating false certainty or promising outcomes that markets cannot guarantee.

## 6. Vision

DarkSage's vision is a transparent, explainable, and customizable trading intelligence platform that helps people transform market information into understanding and disciplined decisions.

The platform should make sophisticated analysis approachable without making it shallow, and make advanced capability powerful without making it needlessly obscure.

## 7. Mission

DarkSage's mission is to:

- organize market evidence into usable context;
- help users explore and test ideas;
- make material risk and uncertainty visible;
- explain analytical conclusions and their limitations;
- support growth in market understanding; and
- preserve user authority over consequential decisions.

## 8. Core Values

### 8.1 Clarity

DarkSage should prefer clear reasoning, consistent terminology, and understandable outcomes over unnecessary complexity.

### 8.2 Evidence

Claims and recommendations should be grounded in identifiable evidence. Inference shall not be presented as fact.

### 8.3 User Authority

The user remains responsible for and in control of investment and trading decisions.

### 8.4 Visible Risk

Material downside, uncertainty, assumptions, and invalidation conditions shall not be hidden to make an opportunity appear more attractive.

### 8.5 Explainability

The platform should help users understand why an analysis matters, not merely present an answer.

### 8.6 Privacy and Security

Privacy and security are product properties to be considered from the beginning, not additions applied after sensitive capabilities exist.

### 8.7 Restraint

Technology, automation, and AI should be used where they create meaningful value. Complexity shall earn its place.

## 9. Product Philosophy

DarkSage should support thoughtful action, including the decision not to act. It should not optimize for engagement, trade frequency, visual spectacle, or artificial confidence.

The platform should:

- prefer understanding over unexplained output;
- prefer honest uncertainty over false precision;
- distinguish observation, calculation, inference, and recommendation;
- use deterministic computation when the problem is deterministic;
- use AI where reasoning, synthesis, explanation, personalization, or natural-language interaction creates meaningful value;
- avoid using AI merely because AI can be used; and
- treat customization as a way to improve relevance and focus, not as a way to change truth.

Recommendations are decision support, not commands. Automation shall be explicit, bounded, observable, and controlled by the user within approved safety systems.

## 10. User Promise

DarkSage should earn trust by making the following product-level commitments:

- It will seek to clarify rather than overwhelm.
- It will distinguish evidence from inference.
- It will communicate material uncertainty and risk.
- It will not present historical results as guaranteed future outcomes.
- It will not silently turn advisory behavior into execution authority.
- It will not treat generative output as authoritative financial calculation.
- It will make consequential capability changes explicit.
- It will preserve the user's ability to question, inspect, and decline recommendations.

These promises constrain product design; they do not promise profit, prediction accuracy, or freedom from loss.

## 11. The DarkSage Constitution

The following principles are intended to remain durable across product versions:

1. **User Authority:** consequential decisions remain under explicit user authority.
2. **Wisdom Over Noise:** information is valuable only when transformed into relevant understanding.
3. **Evidence Before Hype:** claims shall be proportionate to their evidence.
4. **Explainability by Default:** important conclusions should expose their reasoning, assumptions, and limitations.
5. **Visible Risk:** material downside and uncertainty shall not be concealed.
6. **Deterministic Financial Truth:** material financial calculations shall come from deterministic implementations.
7. **Sage Advises; the User Decides:** Sage supports judgment and never becomes unquestionable authority.
8. **Privacy by Design:** collect, expose, and transmit only what is justified.
9. **Presentation Independence:** workspace layout shall not determine underlying analytical capability.
10. **No Silent Capability Changes:** authority, integrations, permissions, data access, and enabled capabilities change only through explicit action.
11. **Earned Complexity:** features and abstractions shall provide meaningful user value.
12. **Codex-Driven Engineering:** major features, requirements, and material decisions enter the DarkSage Codex before implementation.
13. **Leave the System Better Than You Found It:** changes should improve clarity, safety, maintainability, or user value without quietly weakening existing guarantees.

## 12. AI Philosophy

**FOUNDATIONAL PRINCIPLE**

**Sage advises. The user decides.**

Sage is DarkSage's intelligence and AI-assistance layer. Sage should assist rather than replace judgment. It should explain reasoning, identify supporting evidence, communicate uncertainty, surface meaningful risks, and describe what could invalidate a conclusion.

Sage shall:

- distinguish evidence from inference;
- avoid unsupported certainty;
- avoid fabricating deterministic financial results;
- respect explicit user authority;
- never silently escalate from advice to execution authority; and
- never bypass or silently override the Risk Engine.

Sage should use enabled system intelligence when relevant, regardless of whether corresponding widgets are visible in the current workspace. Its available evidence is governed by enabled capabilities, permissions, integrations, configuration, and data—not by presentation layout.

Generative AI is appropriate when reasoning, synthesis, explanation, personalization, or natural-language interaction adds value. It is not the correct authority for deterministic financial calculations. Detailed Sage behavior, evidence governance, memory, and AI boundaries are delegated to DS-003.

## 13. Risk Philosophy

**FOUNDATIONAL PRINCIPLE**

Risk is part of the decision, not an inconvenient footnote.

DarkSage shall preserve the following principles:

- Material risk remains visible.
- Risk shall not be hidden to make an opportunity appear more attractive.
- Sage cannot bypass or silently override the Risk Engine.
- Risk controls remain independently enforceable.
- Analysis should consider downside as well as upside.
- Confidence is not equivalent to safety.
- Historical performance is not a guarantee of future performance.
- Backtest results shall not be presented as guaranteed future outcomes.
- Risk information should be understandable to the intended user.

Any future capability involving execution authority requires approved requirements, permissions, risk controls, and architecture before implementation. DS-001 does not approve or design live trading.

## 14. Privacy Philosophy

DarkSage should apply privacy by design and data minimization. Users should retain practical control over their personal data and external connections.

**CURRENT PRODUCT DIRECTION**

Local-first processing and storage are preferred where practical, appropriate, and consistent with product value. This preference is not an absolute promise that all processing will always remain local or that no data will ever leave a device.

DarkSage should:

- minimize collection and transmission of data;
- handle credentials and secrets securely;
- avoid exposing secrets in logs, examples, documentation, or client-visible output;
- make justified external-service use understandable to the user; and
- avoid unsupported claims of regulatory compliance.

External services may be used when justified by approved architecture, user value, privacy boundaries, and explicit configuration.

## 15. Explainability Standard

When relevant to a material conclusion or recommendation, DarkSage should help the user answer:

- Why did the system reach this conclusion?
- What evidence supports it?
- How strong and current is that evidence?
- What uncertainty exists?
- What material risks are present?
- Which assumptions matter?
- What would invalidate the conclusion?
- What changed from the previous assessment?

Explainability shall not become a performance of certainty. An explanation should expose limitations and conflicts rather than conceal them behind polished language.

DarkSage should clearly distinguish deterministic results, observed data, inferred context, and advisory interpretation. When the available evidence is insufficient, the correct answer may be uncertainty, abstention, or a request for more information.

## 16. Presentation Independence

**FOUNDATIONAL PRINCIPLE**

The user interface is a view into DarkSage's capabilities; it is not the definition of those capabilities.

- Hiding a widget shall not disable an underlying enabled capability.
- Moving a widget shall not change analytical behavior.
- Removing a widget from a workspace shall not remove enabled system intelligence.
- Sage's access to enabled evidence shall not depend on widget visibility.
- Capability changes shall occur only through explicit changes to features, permissions, integrations, data sources, or configuration.

Workspace customization is presentation. Capability is system state. These concepts shall remain separate.

## 17. Product Identity and Terminology

DarkSage may present two compatible vocabularies:

1. themed, Codex-inspired terminology that gives the product character; and
2. plain professional terminology that remains immediately understandable.

Conceptual mappings may include:

| Themed term | Plain professional term |
|---|---|
| Observatory | Market Data / Market Intelligence |
| Watchtower | Scanner |
| Forge | Strategy Builder / Strategy Lab |
| Chronicle | Backtesting / Historical Analysis |
| Guardian | Risk Engine |
| Treasury | Portfolio |
| Sage | AI Assistant / Intelligence Assistant |

These mappings are examples, not final UI-label requirements. Users should not be forced to learn themed terminology to use professional financial tooling. Character shall not reduce clarity, accessibility, or precision.

## 18. Target Users

DarkSage is intended for broad groups that value explainable decision support:

- beginners learning markets;
- self-directed retail investors;
- active traders;
- strategy researchers;
- technically advanced and power users; and
- users dissatisfied with opaque signals or unexplained recommendations.

Beginner-friendly does not mean simplistic. Advanced does not mean incomprehensible. Complexity should be progressively disclosed, meaningful defaults should provide a sound starting point, and capable users should not be artificially prevented from accessing power features.

The product should help users grow in understanding over time rather than make them permanently dependent on unexplained outputs.

## 19. Product Experience Principles

DarkSage experiences should demonstrate:

- clarity before clutter;
- progressive disclosure;
- fast access to important information;
- customization without chaos;
- consistent terminology;
- visible data freshness and provenance where relevant;
- meaningful and safe defaults;
- graceful degradation when capabilities or data are unavailable;
- understandable errors;
- predictable consequences for user actions;
- appropriate confirmation for consequential changes; and
- power without unnecessary complexity.

### 19.1 Workspace Studio Vision

**CURRENT PRODUCT DIRECTION**

Workspace Studio is the high-level vision for customizable dashboards and workspaces. It may support drag-and-drop layout, resizable components, saved layouts, purpose-specific workspaces, user-selected information density, and multi-monitor workflows.

Beginner-friendly defaults should coexist with advanced customization. Users should be able to create clean interfaces containing only the information they care to see without reducing the intelligence available to enabled system capabilities.

This vision does not select a UI framework, persistence format, or layout implementation.

### 19.2 Trading Knowledge and Education

DarkSage should help users understand terminology, indicators, strategies, risk concepts, market behavior, and why an analysis matters. Education should be contextual where practical and should support evidence-based learning rather than unquestionable doctrine.

A Trading Knowledge Engine or equivalent educational intelligence may organize and support this product direction. Detailed requirements, validation rules, content provenance, and curriculum implementation belong in later Codex volumes.

## 20. Platform Boundaries

**CURRENT PRODUCT DIRECTION**

DarkSage is desktop-first. The desktop experience is the primary current product direction.

Desktop-first does not prohibit future APIs, companion applications, mobile or web experiences, cloud-assisted services, integrations, or collaborative services. Those possibilities are not committed deliverables unless approved in the appropriate requirements and roadmap volumes.

DarkSage shall preserve user authority across platforms. No client, presentation surface, or assistant may silently gain execution authority merely because it exists on a different platform.

## 21. Non-Goals

DarkSage is not:

- a promise of profit;
- a guaranteed market predictor;
- a substitute for user judgment;
- an opaque autonomous trader;
- a system where AI output is unquestionable truth;
- a system that hides risk to make recommendations attractive;
- a system where UI layout silently changes analytical capability; or
- a platform that uses generative AI as the authoritative engine for deterministic financial calculations.

DS-001 is not:

- the detailed software requirements specification;
- the technical architecture;
- the database schema;
- the API specification;
- the complete Sage behavior specification; or
- approval for future live-trading implementation.

## 22. Long-Term Vision

**FUTURE ASPIRATION — NOT A COMMITTED REQUIREMENT**

Potential future directions may include:

- broader asset classes and markets;
- richer data integrations;
- deeper strategy and portfolio intelligence;
- personalized Sage Memory;
- collaborative or social capabilities;
- advanced professional workflows;
- additional platforms and companion experiences;
- deeper automation under explicit user control; and
- richer educational intelligence.

These possibilities express ambition, not delivery commitments. Each requires its own evidence, approved requirements, risk review, architectural decisions, and roadmap placement before implementation.

## 23. Governance Relationship

Markdown is the engineering source of truth. Word and PDF editions are publication artifacts derived from approved Markdown content.

The DarkSage Codex divides authority as follows:

| Document | Authority |
|---|---|
| DS-001 | Product philosophy, identity, durable principles, and high-level boundaries |
| DS-002 | Detailed product and software requirements |
| DS-003 | Detailed Sage behavior, boundaries, evidence, memory, reasoning, and AI governance |
| DS-004 | Technical architecture |
| DS-005 | Database and data design |
| DS-006 | API and integration contracts |
| DS-007 | UI/UX system |
| DS-008 | Security architecture |
| DS-009 | Testing and quality assurance |
| DS-010 | Development standards |
| DS-011 | Roadmap |
| DS-012 | Architecture Decision Records |
| DS-013 | Feature backlog |
| DS-014 | Idea parking lot |

Major features should enter the Codex before implementation. Approved requirements shall not be silently changed. Material architectural decisions should be captured through ADRs.

DS-001 constrains lower-level documents but does not preempt the detail assigned to them. If a lower-level proposal appears to conflict with DS-001, the conflict shall be documented and resolved through the controlled review process.

## 24. Glossary

| Term | Meaning |
|---|---|
| DarkSage | The trading intelligence and decision-support platform governed by the DarkSage Codex |
| The DarkSage Codex | DarkSage's authoritative engineering documentation and governance system |
| Sage | DarkSage's intelligence and AI-assistance layer |
| User authority | The principle that consequential investment, trading, automation, and permission decisions remain explicitly controlled by the user within approved safeguards |
| Deterministic financial truth | Material financial results produced by deterministic, testable calculations rather than generative output |
| Presentation independence | Separation between workspace appearance and enabled analytical capability |
| Workspace Studio | The product vision for customizable workspaces and dashboards |
| Trading Knowledge Engine | Product-level educational intelligence for organizing, explaining, and contextualizing trading knowledge; detailed authority belongs to later volumes |
| Current product direction | An approved directional boundary that guides planning but is not itself a detailed feature specification |
| Future aspiration | A possible future direction that is not a committed requirement or delivery promise |

## 25. References

- `docs/CODEX_INDEX.md`
- `docs/standards/DOCUMENTATION_STANDARD.md`
- `docs/standards/STYLE_GUIDE.md`
- `docs/standards/WRITING_GUIDE.md`
- `docs/standards/BRAND_GUIDE.md`
- `docs/codex/Volume-12-ADRs/ADR-001-Desktop-First-Application.md`
- `docs/codex/Volume-12-ADRs/ADR-002-Sage-Cannot-Bypass-the-Risk-Engine.md`
- `docs/codex/Volume-12-ADRs/ADR-003-Deterministic-Financial-Calculations.md`
- `docs/codex/Volume-12-ADRs/ADR-004-Presentation-Independence.md`

## Appendix A — Foundational Principles

1. Technology should help people think more clearly, not think for them.
2. Wisdom Over Noise.
3. Sage advises. The user decides.
4. Evidence shall be distinguishable from inference.
5. Honest uncertainty is better than false precision.
6. Material risk shall remain visible.
7. Deterministic financial results require deterministic calculations.
8. Privacy and security are product properties.
9. Workspace presentation shall not determine enabled capability.
10. Automation and authority shall change only through explicit user action and approved safeguards.
11. Complexity shall earn its place.
12. Major features and material decisions enter the Codex before implementation.

## Appendix B — Open Questions

No unresolved product-foundation questions are currently recorded.
