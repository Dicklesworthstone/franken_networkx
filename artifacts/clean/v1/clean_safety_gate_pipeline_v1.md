# Clean Safety Gate Pipeline

- artifact id: `clean-safety-gate-pipeline-v1`
- generated at (utc): `2026-02-15T16:38:00Z`

## Gate Matrix
| gate id | type | owner | output artifact |
|---|---|---|---|
| GATE-STATIC-FMT | static | release-engineering | artifacts/clean/latest/clean_safety_gate_pipeline_validation_v1.json |
| GATE-STATIC-CLIPPY | static | quality-engineering | artifacts/conformance/latest/logging_final_gate_report_v1.json |
| GATE-DYNAMIC-UNSAFE-POLICY | dynamic | safety-audit | artifacts/clean/latest/clean_unsafe_policy_validation_v1.json |
| GATE-DYNAMIC-PROVENANCE | dynamic | compat-audit | artifacts/clean/latest/clean_provenance_validation_v1.json |
| GATE-DYNAMIC-CLEAN-COMPLIANCE | dynamic | compliance-audit | artifacts/clean/latest/clean_safety_gate_pipeline_validation_v1.json |
| GATE-DYNAMIC-READWRITE-PARSER | dynamic | io-hardening | artifacts/conformance/latest/generated_readwrite_roundtrip_strict_json.report.json |
| GATE-DYNAMIC-RUNTIME-STATE | dynamic | runtime-safety | artifacts/conformance/latest/generated_runtime_config_optional_strict_json.report.json |

## High-Risk Coverage
| target id | category | risk | coverage modes | triage bucket |
|---|---|---|---|---|
| HR-READWRITE-PARSER | parser | high | ['unit', 'property', 'differential', 'e2e'] | parser-malformed-input |
| HR-RUNTIME-STATE | state_transition | high | ['unit', 'property', 'differential', 'e2e'] | state-transition-invariant |
| HR-UNSAFE-POLICY | policy | high | ['unit', 'property', 'differential', 'e2e'] | policy-regression |
| HR-CLEAN-COMPLIANCE | compliance_traceability | high | ['unit', 'property', 'differential', 'e2e'] | policy-regression |

## Artifact Index
- `clean_unsafe_policy_validation` path=`artifacts/clean/latest/clean_unsafe_policy_validation_v1.json` producer=`GATE-DYNAMIC-UNSAFE-POLICY`
- `clean_provenance_validation` path=`artifacts/clean/latest/clean_provenance_validation_v1.json` producer=`GATE-DYNAMIC-PROVENANCE`
- `clean_compliance_audit_log` path=`artifacts/clean/latest/clean_compliance_audit_log_v1.json` producer=`GATE-DYNAMIC-CLEAN-COMPLIANCE`
- `readwrite_roundtrip_report` path=`artifacts/conformance/latest/generated_readwrite_roundtrip_strict_json.report.json` producer=`GATE-DYNAMIC-READWRITE-PARSER`
- `runtime_config_report` path=`artifacts/conformance/latest/generated_runtime_config_optional_strict_json.report.json` producer=`GATE-DYNAMIC-RUNTIME-STATE`
- `structured_logging_gate_report` path=`artifacts/conformance/latest/logging_final_gate_report_v1.json` producer=`GATE-STATIC-CLIPPY`
- `clean_safety_gate_pipeline_validation` path=`artifacts/clean/latest/clean_safety_gate_pipeline_validation_v1.json` producer=`GATE-STATIC-FMT`

## Compliance Scenarios
| scenario id | level | controls | audit log |
|---|---|---|---|
| CLEAN-COMP-UNIT-PROVENANCE-SAFETY | unit | ['provenance_lineage', 'unsafe_policy_fail_closed'] | artifacts/clean/latest/clean_compliance_audit_log_v1.json |
| CLEAN-COMP-E2E-TRACEABILITY | e2e | ['provenance_lineage', 'safety_gate_reproducibility'] | artifacts/clean/latest/clean_compliance_audit_log_v1.json |

## Audit Logging Contract
- path: `artifacts/clean/latest/clean_compliance_audit_log_v1.json`
- required fields: ['claim_id', 'source_anchor', 'implementation_ref', 'reviewer_id', 'mode', 'outcome', 'replay_command', 'triage_metadata']
- mode values: ['strict', 'hardened']
- outcome values: ['pass', 'fail']

## Runtime Contract
- states: ['green', 'yellow', 'red', 'blocked']
- actions: ['run_gate', 'escalate', 'triage', 'block_release']
- loss model: missed high-risk regression > false-negative gate pass > delayed release
- safe mode fallback: block release when any required safety gate fails or artifact index cannot be reconstructed
- safe mode budget: {'max_failed_required_gates': 0, 'max_unmapped_high_risk_targets': 0, 'max_missing_artifact_links': 0}
