# E2E Scenario Matrix Artifacts

This directory stores machine-auditable scenario/oracle contract outputs for bead `bd-315.6.1`.

## Outputs

- `v1/e2e_scenario_matrix_oracle_contract_v1.json`:
  canonical strict/hardened scenario matrix with fixture IDs, deterministic seeds, oracle assertions, and failure-class mapping.
- `v1/e2e_scenario_matrix_oracle_contract_v1.md`:
  compact human-readable matrix summary.
- `schema/v1/e2e_scenario_matrix_oracle_contract_schema_v1.json`:
  schema contract used by fail-closed validation.

## Validation + Gate

```bash
./scripts/generate_e2e_scenario_matrix.py
```

```bash
./scripts/validate_e2e_scenario_matrix.py \
  --artifact artifacts/e2e/v1/e2e_scenario_matrix_oracle_contract_v1.json \
  --schema artifacts/e2e/schema/v1/e2e_scenario_matrix_oracle_contract_schema_v1.json
```

```bash
./scripts/run_e2e_scenario_matrix_gate.sh
```

The gate script emits step logs and report artifacts in `artifacts/e2e/latest/`.
