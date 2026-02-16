# E2E Scenario + Script-Pack Artifacts

This directory stores machine-auditable E2E artifacts for the `bd-315.6.*` chain.

## Scenario Matrix Outputs (`bd-315.6.1`)

- `v1/e2e_scenario_matrix_oracle_contract_v1.json`:
  canonical strict/hardened scenario matrix with fixture IDs, deterministic seeds, oracle assertions, and failure-class mapping.
- `v1/e2e_scenario_matrix_oracle_contract_v1.md`:
  compact human-readable matrix summary.
- `schema/v1/e2e_scenario_matrix_oracle_contract_schema_v1.json`:
  schema contract used by fail-closed validation.

## Cross-Packet Golden Journey Outputs (`bd-315.6.2`..`bd-315.6.4`)

The cross-packet script-pack gate emits:

- `latest/e2e_script_pack_gate_report_v1.json`: pass/fail gate summary.
- `latest/e2e_script_pack_bundle_index_v1.json`: machine-indexable bundle manifest map per scenario.
- `latest/e2e_script_pack_determinism_report_v1.json`: baseline/replay determinism checks.
- `latest/e2e_script_pack_replay_report_v1.json`: replay-drill result with expected vs observed forensics links.
- `latest/e2e_script_pack_events_v1.jsonl`: per-run event stream.
- `latest/e2e_script_pack_steps_v1.jsonl`: per-step gate execution stream.

## Local Entrypoints

Cross-packet golden gate (recommended):

```bash
bash ./scripts/e2e/run_cross_packet_golden.sh
```

Direct gate invocation:

```bash
bash ./scripts/run_e2e_script_pack_gate.sh
```

Per-scenario wrappers:

```bash
bash ./scripts/e2e/run_happy_path.sh
bash ./scripts/e2e/run_edge_path.sh
bash ./scripts/e2e/run_malformed_input.sh
```

Replay drill (single manifest):

```bash
python3 ./scripts/run_e2e_script_pack.py \
  --replay-manifest artifacts/e2e/latest/bundles/malformed_input/baseline/bundle_manifest_v1.json \
  --output-dir artifacts/e2e/latest
```

## CI Entrypoint

Workflow file:

- `.github/workflows/e2e-cross-packet-golden.yml`

Workflow behavior:

1. Checks out repo and installs Rust toolchain.
2. Runs `bash ./scripts/e2e/run_cross_packet_golden.sh`.
3. Uploads `artifacts/e2e/latest/` as workflow artifact for forensics/replay.

## Flake Triage Protocol (Quarantine + Replay Proof)

When cross-packet gate fails in CI or local:

1. Capture step and gate reports:
   - `artifacts/e2e/latest/e2e_script_pack_gate_report_v1.json`
   - `artifacts/e2e/latest/e2e_script_pack_steps_v1.jsonl`
2. Quarantine the flaking scenario by isolating it to wrapper replay:
   - `bash ./scripts/e2e/run_happy_path.sh` or edge/malformed equivalent.
3. Mandatory replay proof:
   - run `--replay-manifest` for the failing scenario bundle manifest.
   - require `e2e_script_pack_replay_report_v1.json` with `"status": "passed"` and `"forensics_match": true` before unquarantine.
4. Keep failing run artifacts under `artifacts/e2e/latest/` and attach the uploaded CI artifact to the bead/thread.

No unquarantine without replay proof and deterministic forensics linkage.
