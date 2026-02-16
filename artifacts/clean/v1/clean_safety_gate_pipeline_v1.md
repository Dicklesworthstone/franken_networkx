# Clean Safety Gate Pipeline

- artifact id: `clean-safety-gate-pipeline-v1`
- generated at (utc): `2026-02-16T20:45:36Z`

## Gate Matrix
| gate id | type | owner | output artifact |
|---|---|---|---|
| GATE-STATIC-FMT | static | release-engineering | artifacts/clean/latest/clean_safety_gate_pipeline_validation_v1.json |
| GATE-STATIC-CLIPPY | static | quality-engineering | artifacts/conformance/latest/logging_final_gate_report_v1.json |
| GATE-DYNAMIC-UNSAFE-POLICY | dynamic | safety-audit | artifacts/clean/latest/clean_unsafe_policy_validation_v1.json |
| GATE-DYNAMIC-PROVENANCE | dynamic | compat-audit | artifacts/clean/latest/clean_provenance_validation_v1.json |
| GATE-DYNAMIC-READWRITE-PARSER | dynamic | io-hardening | artifacts/conformance/latest/generated_readwrite_roundtrip_strict_json.report.json |
| GATE-DYNAMIC-RUNTIME-STATE | dynamic | runtime-safety | artifacts/conformance/latest/generated_runtime_config_optional_strict_json.report.json |

## High-Risk Coverage
| target id | category | risk | coverage modes | triage bucket |
|---|---|---|---|---|
| HR-READWRITE-PARSER | parser | high | ['unit', 'property', 'differential', 'e2e'] | parser-malformed-input |
| HR-RUNTIME-STATE | state_transition | high | ['unit', 'property', 'differential', 'e2e'] | state-transition-invariant |
| HR-UNSAFE-POLICY | policy | high | ['unit', 'property', 'differential', 'e2e'] | policy-regression |

## Artifact Index
- `clean_unsafe_policy_validation` path=`artifacts/clean/latest/clean_unsafe_policy_validation_v1.json` producer=`GATE-DYNAMIC-UNSAFE-POLICY`
- `clean_provenance_validation` path=`artifacts/clean/latest/clean_provenance_validation_v1.json` producer=`GATE-DYNAMIC-PROVENANCE`
- `readwrite_roundtrip_report` path=`artifacts/conformance/latest/generated_readwrite_roundtrip_strict_json.report.json` producer=`GATE-DYNAMIC-READWRITE-PARSER`
- `runtime_config_report` path=`artifacts/conformance/latest/generated_runtime_config_optional_strict_json.report.json` producer=`GATE-DYNAMIC-RUNTIME-STATE`
- `structured_logging_gate_report` path=`artifacts/conformance/latest/logging_final_gate_report_v1.json` producer=`GATE-STATIC-CLIPPY`
- `clean_safety_gate_pipeline_validation` path=`artifacts/clean/latest/clean_safety_gate_pipeline_validation_v1.json` producer=`GATE-STATIC-FMT`

## Fail-Closed Policy
- unknown incompatible features: `fail_closed`
- missing artifact links: `fail_closed`
- violation action: `block_release_and_emit_audit_record`
- audit log: `artifacts/clean/latest/clean_compliance_audit_log_v1.json`

## Operator Triage Playbook
- primary oncall role: `safety-audit`
- step `FR-1` owner=`release-engineering` sla_min=15 action=Acknowledge incident and freeze release promotion path.
- step `FR-2` owner=`safety-audit` sla_min=30 action=Collect deterministic replay command, failure envelope, and artifact index references.
- step `FR-3` owner=`runtime-safety` sla_min=45 action=Assign triage bucket owner and open escalation thread with evidence links.
- escalation `ESC-UNKNOWN-INCOMPATIBLE` if `reason_code == unknown_incompatible_feature` -> `compat-audit` within 30m (severity >= critical)
- escalation `ESC-MISSING-ARTIFACT-LINK` if `reason_code == missing_artifact_link` -> `release-engineering` within 30m (severity >= critical)

## Dashboard Contract
- path: `artifacts/clean/latest/clean_safety_gate_pipeline_dashboard_v1.json`
- deterministic ordering: `lexicographic`
- deterministic sort keys: `['gate_id', 'target_id', 'bucket_id']`
- audit mode: `append_only`

## Runtime Contract
- states: ['green', 'yellow', 'red', 'blocked']
- actions: ['run_gate', 'escalate', 'triage', 'block_release']
- loss model: missed high-risk regression > false-negative gate pass > delayed release
- safe mode fallback: block release when any required safety gate fails or artifact index cannot be reconstructed
- safe mode budget: {'max_failed_required_gates': 0, 'max_unmapped_high_risk_targets': 0, 'max_missing_artifact_links': 0}
