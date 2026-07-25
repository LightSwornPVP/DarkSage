<!--
Page Type: Requirement Page / Card (DSF-001 §E.8, §F "Requirement Card"; DSF-003 §8.2)
Use: presenting one DS-<DOMAIN>-NNN requirement (Codex Complete Edition) or one consolidated PRS entry.
Page-break behavior: the ID/Title header row and Release Classification badge never separate from the start of the card's own body content across a page break.
Mandatory disclaimer (every card, DSF-003 §8.2): "This card is a derived summary. The controlling requirement text in the cited Codex volume governs."
-->

### {{RequirementID}} — {{RequirementTitle}}

**Status/Classification:** {{CommittedMVP_or_Planned_or_FutureExploratory}}
**Priority:** {{Critical_High_Medium_Low}}
**Controlling Source:** {{ControllingRequirementID}}

**Purpose / Description**
{{PurposeDescription}}

**Acceptance Criteria**
- [ ] {{Criterion}}

**Edge Cases**
- {{EdgeCase}}

**Dependencies:** {{DependencyIDList}}

**Testing:** {{TestingDirection}}

**Traceability:** {{Requirement}} → {{DesignADR}} → {{Source}} → {{Test}} → {{ReleaseChange}}

> This card is a derived summary. The controlling requirement text in the cited Codex volume governs.
