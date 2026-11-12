# asupersync Fault-Injection + Property Test Suite (V1)

- generated_at_utc: `2026-02-15T20:44:00+00:00`
- baseline_comparator: `legacy_networkx/main@python3.12 + asupersync@0.2.0`

## Covered Fault Classes

| Fault ID | Type | Expected Reason | Expected Terminal State |
|---|---|---|---|
| `ASUP-FAULT-001` | `interruption` | `retry_exhausted` | `failed_closed` |
| `ASUP-FAULT-002` | `partial_write` | `conflict_detected` | `failed_closed` |
| `ASUP-FAULT-003` | `checksum_mismatch` | `integrity_precheck_failed` | `failed_closed` |
| `ASUP-FAULT-004` | `stale_metadata` | `resume_seed_mismatch` | `failed_closed` |

## Structured Log Contract

Required fields:

- `transfer_id`
- `artifact_id`
- `retry_count`
- `mode`
- `seed`
- `env_fingerprint`
- `outcome_reason_code`
- `replay_command`

## Repro Commands

- `ASUP-FAULT-001`: `rch exec -- env CARGO_TARGET_DIR=target-codex-mossy cargo test -p fnx-runtime asupersync_adapter_retry_budget_exhaustion_fault_injection_is_fail_closed -- --nocapture`
- `ASUP-FAULT-002`: `rch exec -- env CARGO_TARGET_DIR=target-codex-mossy cargo test -p fnx-runtime asupersync_adapter_partial_write_cursor_regression_is_fail_closed -- --nocapture`
- `ASUP-FAULT-003`: `rch exec -- env CARGO_TARGET_DIR=target-codex-mossy cargo test -p fnx-runtime asupersync_adapter_checksum_mismatch_is_fail_closed_and_audited -- --nocapture`
- `ASUP-FAULT-004`: `rch exec -- env CARGO_TARGET_DIR=target-codex-mossy cargo test -p fnx-runtime asupersync_adapter_stale_metadata_seed_mismatch_rejects_resume -- --nocapture`

## Property Coverage

- deterministic property test: `asupersync_adapter_property_same_fault_sequence_has_identical_transitions`
- invariant: identical seed + fault sequence must produce identical transition logs
