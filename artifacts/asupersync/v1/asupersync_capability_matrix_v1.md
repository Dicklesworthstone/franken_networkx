# asupersync Capability Matrix + Integration Boundary Contract (V1)

- generated_at_utc: `2026-02-15T19:23:00+00:00`
- baseline_comparator: `legacy_networkx/main@python3.12 + asupersync@0.2.0`
- owning_crate: `fnx-runtime`
- feature_gate: `asupersync-integration`

## Capability Rows

| Operation | Artifact Class | Strict Unsupported Policy | Hardened Unsupported Policy | Default Action |
|---|---|---|---|---|
| `ASUP-CAP-001` | `conformance_fixture_bundle` | `fail_closed` | `fail_closed` | `abort_sync` |
| `ASUP-CAP-002` | `benchmark_baseline_bundle` | `fail_closed` | `fail_closed` | `abort_sync` |
| `ASUP-CAP-003` | `migration_manifest` | `fail_closed` | `fail_closed` | `abort_sync` |
| `ASUP-CAP-004` | `reproducibility_ledger` | `fail_closed` | `fail_closed` | `abort_sync` |
| `ASUP-CAP-005` | `long_lived_state_snapshot` | `fail_closed` | `fail_closed` | `abort_sync` |

## Integration Boundary

- allowed runtime crates:
  - `fnx-runtime`
  - `fnx-durability`
  - `fnx-conformance`
- forbidden algorithm crates:
  - `fnx-classes`
  - `fnx-views`
  - `fnx-algorithms`
  - `fnx-dispatch`
  - `fnx-convert`
  - `fnx-generators`
  - `fnx-readwrite`

## Required Telemetry Fields

`transfer_id`, `artifact_id`, `artifact_class`, `mode`, `primitive`, `attempt`, `outcome`, `reason_code`, `seed`, `replay_command`, `env_fingerprint`, `duration_ms`
