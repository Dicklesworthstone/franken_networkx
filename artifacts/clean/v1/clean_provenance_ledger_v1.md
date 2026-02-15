# Clean-Room Provenance Ledger

- artifact id: `clean-provenance-ledger-v1`
- generated at (utc): `2026-02-15T05:14:27Z`
- baseline comparator: `legacy_networkx_code/networkx/networkx source anchors + in-repo Rust implementation artifacts`

## Scope
Machine-checkable clean-room provenance ledger covering extraction claims, implementation refs, handoff boundaries, ambiguity decisions, and reviewer sign-off.

## Parity + Optimization Contracts
- drop-in parity target: `100%`
- optimization lever policy: `exactly_one_optimization_lever_per_change` (max=1)

## Separation Workflow
- workflow id: `clean-room-provenance-separation-v1`
- principles:
  - Extraction role captures behavior only; no Rust implementation edits in extraction stage.
  - Implementation role consumes extraction artifacts and must not modify legacy-source extraction records.
  - Review role verifies lineage completeness and separation controls before parity gate promotion.
- stages:
  - `S1` `legacy_extraction` owner=`legacy-extraction-agent` inputs=['legacy_networkx_code/networkx/networkx/**'] outputs=['artifacts/phase2c/FNX-P2C-*/legacy_anchor_map.md'] must_not_modify=['crates/**']
  - `S2` `contract_linking` owner=`contract-agent` inputs=['artifacts/phase2c/FNX-P2C-*/legacy_anchor_map.md'] outputs=['artifacts/phase2c/FNX-P2C-*/contract_table.md', 'artifacts/clean/v1/clean_provenance_ledger_v1.json'] must_not_modify=['legacy_networkx_code/**']
  - `S3` `rust_implementation` owner=`rust-implementation-agent` inputs=['artifacts/phase2c/FNX-P2C-*/contract_table.md'] outputs=['crates/**', 'artifacts/phase2c/FNX-P2C-*/parity_report.json'] must_not_modify=['legacy_networkx_code/**']
  - `S4` `review_and_signoff` owner=`reviewer` inputs=['artifacts/clean/v1/clean_provenance_ledger_v1.json', 'artifacts/phase2c/FNX-P2C-*/parity_report.json'] outputs=['reviewer_signoff status + notes'] must_not_modify=['legacy extraction content without new extraction evidence']
- handoff controls:
  - `HC-1` Every provenance record must include explicit extractor/implementer boundary and handoff artifact path. evidence=`provenance_records[].handoff_boundary` enforcement=`validator + conformance gate`
  - `HC-2` Reviewer sign-off is mandatory for each record before final readiness. evidence=`provenance_records[].reviewer_signoff` enforcement=`validator + conformance gate`
  - `HC-3` Ambiguity decisions require confidence rating and rationale. evidence=`ambiguity_decisions[]` enforcement=`validator + conformance gate`

## Provenance Records
| record id | packet | family | confidence | reviewer | signoff |
|---|---|---|---|---|---|
| CPR-001 | FNX-P2C-001 | graph_core | 0.96 | compat-audit-reviewer | approved |
| CPR-002 | FNX-P2C-002 | views | 0.93 | compat-audit-reviewer | approved |
| CPR-003 | FNX-P2C-003 | dispatch | 0.95 | security-compat-reviewer | approved |
| CPR-004 | FNX-P2C-004 | convert | 0.94 | compat-audit-reviewer | approved |
| CPR-005 | FNX-P2C-005 | algorithms | 0.92 | algo-parity-reviewer | approved |
| CPR-006 | FNX-P2C-006 | readwrite | 0.95 | io-compat-reviewer | approved |
| CPR-007 | FNX-P2C-007 | generators | 0.93 | determinism-reviewer | approved |
| CPR-008 | FNX-P2C-008 | runtime | 0.94 | runtime-security-reviewer | approved |
| CPR-009 | FNX-P2C-009 | conformance | 0.91 | parity-gate-reviewer | approved |

## Ambiguity Decisions
| decision id | record id | confidence | selected policy |
|---|---|---|---|
| CPR-AMB-001 | CPR-001 | 0.94 | preserve insertion-order LIFO behavior |
| CPR-AMB-002 | CPR-002 | 0.87 | record and tolerate set-union ambiguity; do not canonicalize strict mode |
| CPR-AMB-003 | CPR-003 | 0.95 | fail/skip conversion rather than guess |
| CPR-AMB-004 | CPR-004 | 0.92 | retain fixed probe-order precedence |
| CPR-AMB-005 | CPR-005 | 0.89 | allow legacy-equivalent predecessor permutations |
| CPR-AMB-006 | CPR-007 | 0.90 | preserve input iterable semantics without deduplication |
| CPR-AMB-007 | CPR-009 | 0.88 | record ambiguity allowances explicitly per fixture family |

## Audit Query Index
- `CPR-Q01` Which legacy anchor produced graph-core mutation behavior implemented in fnx-classes and approved for release?
  - record_path: ['CPR-001']
  - expected_end_to_end_fields: ['legacy_source_anchor', 'extracted_behavior_claim', 'implementation_artifact_refs', 'reviewer_signoff', 'conformance_evidence_refs']
- `CPR-Q02` Show full lineage chain from extraction packet 001 through conformance packet 009.
  - record_path: ['CPR-001', 'CPR-002', 'CPR-003', 'CPR-004', 'CPR-005', 'CPR-006', 'CPR-007', 'CPR-008', 'CPR-009']
  - expected_end_to_end_fields: ['legacy_source_anchor', 'extracted_behavior_claim', 'implementation_artifact_refs', 'reviewer_signoff', 'conformance_evidence_refs']
- `CPR-Q03` List ambiguity decisions with confidence for dispatch and shortest-path lineage records.
  - record_path: ['CPR-003', 'CPR-005']
  - expected_end_to_end_fields: ['legacy_source_anchor', 'extracted_behavior_claim', 'implementation_artifact_refs', 'reviewer_signoff', 'conformance_evidence_refs']

## Runtime Contract
- states: ['extract_only', 'implement_only', 'review', 'blocked']
- actions: ['handoff', 'approve', 'reject', 'rework']
- loss model: cross-boundary contamination > missing lineage evidence > delayed handoff
- safe mode fallback: block promotion when provenance lineage is incomplete or signoff missing
- safe mode budget: {'max_blocked_promotions_per_run': 0, 'max_unsigned_records_before_halt': 0, 'max_unresolved_ambiguities_before_halt': 0}
- trigger thresholds:
  - `TRIG-UNSIGNED-RECORD` condition=count(records where reviewer_signoff.status != approved) >= 1 threshold=1 fallback=enter blocked state and reject release promotion
  - `TRIG-INCOMPLETE-LINEAGE` condition=count(records with missing legacy/implementation/conformance linkage) >= 1 threshold=1 fallback=halt handoff and require rework
  - `TRIG-UNMAPPED-AMBIGUITY` condition=count(ambiguity_decisions where confidence_rating < 0.8) >= 1 threshold=1 fallback=require reviewer escalation before approval
