# clean_final_compliance_attestation_v1

- artifact id: `clean-final-compliance-attestation-v1`
- generated at: `2026-02-16T00:30:00Z`
- schema: `artifacts/clean/schema/v1/clean_final_compliance_attestation_schema_v1.json`

## Scope

Final clean-room and memory-safety attestation package for `bd-315.28.6`, consolidating:

- provenance lineage evidence
- unsafe-policy fail-closed enforcement evidence
- safety gate reproducibility evidence
- durability sidecars/decode proofs/integrity scrub reports
- independent replay/signoff package

## Mandatory Replay Commands

- `rch exec -- cargo test -p fnx-conformance clean_provenance_ledger_is_lineage_complete_and_separated -- --exact --nocapture`
- `rch exec -- cargo test -p fnx-conformance clean_unsafe_policy_defaults_are_fail_closed -- --exact --nocapture`
- `rch exec -- cargo test -p fnx-conformance clean_safety_gate_pipeline_is_reproducible_and_artifact_indexed -- --exact --nocapture`
- `rch exec -- cargo test -p fnx-conformance clean_final_compliance_attestation_is_complete_and_signoff_ready -- --exact --nocapture`

## Signoff Rule

Release signoff is permitted only if:

- audit checklist remains all `pass`
- `clean_final_compliance_attestation_validation_v1.json` reports `ready=true` and `error_count=0`
- durability evidence paths are present and resolvable
