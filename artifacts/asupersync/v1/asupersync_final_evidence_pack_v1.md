# asupersync Final Evidence Pack (V1)

- artifact_id: `asupersync-final-evidence-pack-v1`
- generated_at_utc: `2026-02-16T22:27:00Z`
- bead: `bd-315.26.6`

## Included Bundle

- contracts:
  - `asupersync_capability_matrix_v1.json`
  - `asupersync_adapter_state_machine_v1.json`
  - `asupersync_fault_injection_suite_v1.json`
  - `asupersync_performance_characterization_v1.json`
- implementation/test:
  - runtime and conformance gate sources for ASUP A-E
  - `scripts/run_phase2c_readiness_e2e.sh` (includes ASUP performance gate)
- runbook:
  - `artifacts/asupersync/v1/asupersync_operational_runbook_v1.md`

## Durability Attachments

- sidecar: `artifacts/asupersync/v1/asupersync_final_evidence_pack_v1.raptorq.json`
- recovered output: `artifacts/asupersync/v1/asupersync_final_evidence_pack_v1.recovered.json`
- scrub report: `artifacts/asupersync/v1/asupersync_final_evidence_pack_v1_scrub_report.json`

## Sign-off Status

- contract/impl/test/perf/risk bundle: `pass`
- durability sidecar + scrub + decode proof: `pass`
- runbook triage/replay/escalation: `pass`
- reviewer sign-off package complete: `pass`
