# asupersync Operational Runbook (V1)

- owner: `fnx-runtime` + `fnx-conformance`
- scope: ASUP capability contract, adapter state machine, fault-injection suite, performance safety gate, and final evidence bundle
- primary bead: `bd-315.26.6`

## 1. Failure Triage

### A. `unsupported_capability` / `capability_mismatch`

1. Run capability gate:
   - `rch exec -- cargo test -q -p fnx-conformance --test asupersync_capability_matrix_gate -- --nocapture`
2. Confirm `asupersync-integration` feature + crate boundaries:
   - `crates/fnx-runtime/Cargo.toml`
   - `artifacts/asupersync/v1/asupersync_capability_matrix_v1.json`
3. If violation persists, fail closed and escalate to runtime owner.

### B. `integrity_precheck_failed`

1. Run adapter + fault gates:
   - `rch exec -- cargo test -q -p fnx-runtime asupersync_adapter_checksum_mismatch_is_fail_closed_and_audited -- --exact --nocapture`
   - `rch exec -- cargo test -q -p fnx-conformance --test asupersync_fault_injection_gate -- --nocapture`
2. Re-run durability scrub/decode proof:
   - `rch exec -- cargo run -q -p fnx-durability --bin fnx-durability -- scrub artifacts/asupersync/v1/asupersync_final_evidence_pack_v1.json artifacts/asupersync/v1/asupersync_final_evidence_pack_v1.raptorq.json`
   - `rch exec -- cargo run -q -p fnx-durability --bin fnx-durability -- decode-drill artifacts/asupersync/v1/asupersync_final_evidence_pack_v1.raptorq.json artifacts/asupersync/v1/asupersync_final_evidence_pack_v1.recovered.json`
3. Verify decode proof count increments in sidecar.

### C. `retry_exhausted` / `conflict_detected` / `resume_seed_mismatch`

1. Run deterministic adapter suite:
   - `rch exec -- cargo test -q -p fnx-runtime asupersync_adapter_ -- --nocapture`
2. Run E2E replay pack:
   - `bash ./scripts/run_e2e_script_pack_gate.sh`
3. Validate structured event traces:
   - `artifacts/e2e/latest/e2e_script_pack_events_v1.jsonl`

## 2. Replay Workflow

1. Unit + differential replay set:
   - `rch exec -- cargo test -q -p fnx-runtime asupersync_adapter_ -- --nocapture`
   - `rch exec -- cargo test -q -p fnx-conformance --test asupersync_adapter_state_machine_gate -- --nocapture`
   - `rch exec -- cargo test -q -p fnx-conformance --test asupersync_fault_injection_gate -- --nocapture`
   - `rch exec -- cargo test -q -p fnx-conformance --test asupersync_performance_gate -- --nocapture`
2. Full readiness replay:
   - `bash ./scripts/run_phase2c_readiness_e2e.sh`
3. Validate final evidence bundle integrity:
   - `rch exec -- cargo run -q -p fnx-durability --bin fnx-durability -- scrub artifacts/asupersync/v1/asupersync_final_evidence_pack_v1.json artifacts/asupersync/v1/asupersync_final_evidence_pack_v1.raptorq.json`

## 3. Escalation Policy

- P0 security/compatibility drift:
  - strict-mode parity or fail-closed contract broken
  - action: block release + page runtime/conformance owners
- P1 reliability regression:
  - tail metrics exceed ASUP-E thresholds or decode proof fails
  - action: rollback optimization lever, regenerate evidence, rerun full readiness gates
- P2 documentation/evidence drift:
  - missing checklist links, stale artifact paths, non-auditable runbook notes
  - action: refresh bundle and re-sign checklist before next readiness drill

## 4. Operator Checklist

- [ ] capability/state/fault/performance gates pass
- [ ] sidecar generation + scrub + decode-drill pass
- [ ] structured log artifacts present and replayable
- [ ] final evidence bundle references current artifact paths
- [ ] sign-off checklist remains fully `pass`
