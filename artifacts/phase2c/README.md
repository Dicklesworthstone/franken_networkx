# Phase2C Artifact Topology (Locked)

This directory contains the versioned, machine-checkable artifact contract for Phase2C packets.

## Contract Objective

For every packet, the following artifacts are mandatory:

1. `legacy_anchor_map.md`
2. `contract_table.md`
3. `fixture_manifest.json`
4. `parity_gate.yaml`
5. `risk_note.md`
6. `parity_report.json`
7. `parity_report.raptorq.json`

A packet is `NOT READY` if any required artifact is missing or any mandatory field/section is missing.

## Files

- `schema/v1/artifact_contract_schema_v1.json`: canonical versioned artifact contract.
- `schema/v1/packet_topology_schema_v1.json`: topology-manifest schema.
- `schema/v1/essence_extraction_ledger_schema_v1.json`: machine-auditable extraction-ledger schema.
- `schema/v1/security_compatibility_contract_schema_v1.json`: threat/allowlist contract schema.
- `packet_topology_v1.json`: packet topology and required artifact mapping.
- `essence_extraction_ledger_v1.json`: packet-by-packet invariant ledger with verification hooks.
- `security/v1/security_compatibility_threat_matrix_v1.json`: packet-family threat classes + mitigations.
- `security/v1/hardened_mode_deviation_allowlist_v1.json`: explicit hardened-mode deviation categories.
- `templates/`: scaffold templates for required artifacts.

## Validation

```bash
./scripts/validate_phase2c_artifacts.py \
  --topology artifacts/phase2c/packet_topology_v1.json \
  --schema artifacts/phase2c/schema/v1/artifact_contract_schema_v1.json
```

```bash
./scripts/validate_phase2c_security_contracts.py \
  --contract artifacts/phase2c/schema/v1/security_compatibility_contract_schema_v1.json \
  --matrix artifacts/phase2c/security/v1/security_compatibility_threat_matrix_v1.json \
  --allowlist artifacts/phase2c/security/v1/hardened_mode_deviation_allowlist_v1.json
```

```bash
./scripts/validate_phase2c_essence_ledger.py \
  --ledger artifacts/phase2c/essence_extraction_ledger_v1.json \
  --schema artifacts/phase2c/schema/v1/essence_extraction_ledger_schema_v1.json \
  --topology artifacts/phase2c/packet_topology_v1.json
```

```bash
./scripts/run_phase2c_readiness_e2e.sh
```

Non-zero exit code indicates at least one packet is `NOT READY`.
