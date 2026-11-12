# asupersync Adapter + Retry/Resume State Machine (V1)

- generated_at_utc: `2026-02-15T19:46:00+00:00`
- baseline_comparator: `legacy_networkx/main@python3.12 + asupersync@0.2.0`
- owning_crate: `fnx-runtime`
- module_path: `crates/fnx-runtime/src/lib.rs`

## State Model

| State | Terminal |
|---|---|
| `idle` | no |
| `capability_check` | no |
| `syncing` | no |
| `verifying_checksum` | no |
| `completed` | yes |
| `failed_closed` | yes |

## Critical Transitions

| From | Event | To | Reason |
|---|---|---|---|
| `capability_check` | `capability_rejected` | `failed_closed` | `unsupported_capability` |
| `syncing` | `retry_budget_exceeded` | `failed_closed` | `retry_exhausted` |
| `syncing` | `conflict_detected` | `failed_closed` | `conflict_detected` |
| `verifying_checksum` | `checksum_mismatch` | `failed_closed` | `integrity_precheck_failed` |
| `verifying_checksum` | `checksum_validated` | `completed` | `null` |

## Resume Contract

- checkpoint fields: `transfer_id`, `deterministic_seed`, `attempt`, `committed_cursor`
- deterministic rule: identical intent + identical checkpoint must reconstruct equivalent syncing state
- fail-closed triggers:
  - transfer ID mismatch
  - deterministic seed mismatch
  - resume cursor ahead of committed cursor
  - retry budget exhaustion

## Test Bindings

- `ASUP-B-UNIT-001` -> `rch exec -- env CARGO_TARGET_DIR=target-codex-mossy cargo test -p fnx-runtime -- --nocapture`
- `ASUP-B-DIFF-001` -> `rch exec -- env CARGO_TARGET_DIR=target-codex-mossy cargo test -p fnx-conformance --test asupersync_adapter_state_machine_gate -- --nocapture`
- `ASUP-B-E2E-001` -> `rch exec -- env CARGO_TARGET_DIR=target-codex-mossy cargo test -p fnx-conformance --test asupersync_adapter_state_machine_gate -- --nocapture`
