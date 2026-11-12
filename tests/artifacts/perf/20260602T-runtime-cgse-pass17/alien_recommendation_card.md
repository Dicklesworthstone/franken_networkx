# Alien Recommendation Card - br-r37-c1-ghg5y

## Intake
- Project: FrankenNetworkX / `fnx-runtime`
- Workload: `cgse_policy_bench --iterations 2500000 --mode strict`
- Symptom: allocation-heavy policy decision construction in a deterministic runtime control loop
- Baseline artifact: `baseline_strict_hyperfine.json`
- Profile artifact: `profile_breakdown_strict.jsonl`
- Correctness constraints: exact operation strings, rule order, action tie-breaking, NaN/fail-closed handling, timestamps, floating-point clamping, and RNG-free behavior preserved

## Hotspot
| Rank | Location | Metric | Value | Evidence |
|---|---|---:|---:|---|
| 1 | `CgsePolicyEngine::evaluate_at` operation string construction | CPU/allocation component | 233.394888 ms of 941.913229 ms full loop | `profile_breakdown_strict.jsonl` |
| 2 | rationale formatting | CPU/allocation component | 492.633188 ms | `profile_breakdown_strict.jsonl` |
| 3 | evidence vector owned strings | CPU/allocation component | 38.144728 ms | `profile_breakdown_strict.jsonl` |

## Primitive Match
- Graveyard primitive: compiled artifact / offline table to online kernel.
- Canonical hook: precomputed deterministic runtime artifacts replace repeated synthesis work.
- Local translation: compile exact operation names into `CgsePolicyRule::operation_name()` and keep the public `DecisionRecord.operation: String` by cloning the static string.

## EV Gate
| Candidate | Impact | Confidence | Reuse | Effort | Adoption Friction | EV |
|---|---:|---:|---:|---:|---:|---:|
| Static operation-name table | 3 | 5 | 3 | 1 | 1 | 45.0 |
| Rationale static templates | 4 | 4 | 3 | 2 | 2 | 12.0 |

Chosen lever: static operation-name table only.

## Fallback
- Trigger: any golden SHA mismatch, action mismatch, or test failure.
- Fallback: restore the existing `format!("{}::{}", family, rule_id.to_lowercase())` construction.

## Proof Obligations
- `operation_name()` must equal the previous formula for every `CgsePolicyRule::ALL` element.
- Rule order and policy/action tie-breaking are untouched.
- Floating-point clamping and NaN handling are untouched.
- No RNG is used or introduced.
- Golden stdout SHA-256 must match before/after.
