# frankentui Telemetry Adapter + Artifact Index (V1)

- generated_at_utc: `2026-02-15T20:34:00+00:00`
- baseline_comparator: `legacy_networkx/main@python3.12 + frankentui@main`
- owning_crate: `fnx-runtime`
- integration_seam: `ftui_bridge::TelemetryArtifactIndexAdapter`

## Canonical Ingestion Fields

- `run_id`
- `journey_id`
- `event_id`
- `state`
- `seed`
- `artifact_ref`
- `test_id`
- `replay_command`
- `env_fingerprint`
- `duration_ms`

Unknown fields are fail-closed with actionable diagnostics.

## Artifact Index Ordering

Rows are sorted deterministically by:

1. `captured_unix_ms`
2. `run_id`
3. `test_id`
4. `bundle_id`
5. `correlation_id`

## Failure Modes

| Reason Code | Trigger | Action |
|---|---|---|
| `unknown_telemetry_field` | non-canonical field detected | `fail_closed` |
| `incompatible_structured_log` | structured-log validation failure | `fail_closed` |

## Gate Replay

- `FTUI-B-UNIT-001`: `rch exec -- env CARGO_TARGET_DIR=target-codex-mossy cargo test -p fnx-runtime ftui_adapter_ -- --nocapture`
- `FTUI-B-DIFF-001`: `rch exec -- env CARGO_TARGET_DIR=target-codex-mossy cargo test -p fnx-conformance --test ftui_telemetry_adapter_gate -- --nocapture`
