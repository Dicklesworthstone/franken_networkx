# Documentation Pass Artifacts

This directory contains machine-auditable planning artifacts for documentation expansion passes.

## DOC-PASS-00 Outputs

- `v1/doc_pass00_gap_matrix_v1.json`: full section-level baseline gap matrix.
- `v1/doc_pass00_gap_matrix_v1.md`: human-readable top-priority summary table.
- `schema/v1/doc_pass00_gap_matrix_schema_v1.json`: schema contract for matrix structure.

## DOC-PASS-03 Outputs

- `v1/doc_pass03_data_model_state_invariant_v1.json`: component-level data model, state transitions, invariants, and recovery behavior.
- `v1/doc_pass03_data_model_state_invariant_v1.md`: compact component/invariant summary.
- `schema/v1/doc_pass03_data_model_state_invariant_schema_v1.json`: schema contract for DOC-PASS-03 artifact.

## DOC-PASS-05 Outputs

- `v1/doc_pass05_complexity_perf_memory_v1.json`: operation-level complexity, memory-growth, hotspot hypotheses, and optimization parity risk notes.
- `v1/doc_pass05_complexity_perf_memory_v1.md`: compact family/operation complexity summary.
- `schema/v1/doc_pass05_complexity_perf_memory_schema_v1.json`: schema contract for DOC-PASS-05 artifact.

## Commands

```bash
./scripts/generate_doc_gap_matrix.py
```

```bash
./scripts/validate_doc_gap_matrix.py \
  --matrix artifacts/docs/v1/doc_pass00_gap_matrix_v1.json \
  --schema artifacts/docs/schema/v1/doc_pass00_gap_matrix_schema_v1.json
```

```bash
./scripts/run_doc_pass00_gap_matrix.sh
```

```bash
./scripts/generate_doc_pass03_state_mapping.py
```

```bash
./scripts/validate_doc_pass03_state_mapping.py \
  --artifact artifacts/docs/v1/doc_pass03_data_model_state_invariant_v1.json \
  --schema artifacts/docs/schema/v1/doc_pass03_data_model_state_invariant_schema_v1.json
```

```bash
./scripts/run_doc_pass03_state_mapping.sh
```

```bash
./scripts/generate_doc_pass05_complexity_perf_memory.py
```

```bash
./scripts/validate_doc_pass05_complexity_perf_memory.py \
  --artifact artifacts/docs/v1/doc_pass05_complexity_perf_memory_v1.json \
  --schema artifacts/docs/schema/v1/doc_pass05_complexity_perf_memory_schema_v1.json
```

```bash
./scripts/run_doc_pass05_complexity_perf_memory.sh
```
