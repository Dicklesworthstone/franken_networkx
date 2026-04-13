# Perf History

This directory stores per-run historical performance records derived from
`artifacts/perf/phase2c/perf_baseline_matrix_events_v1.jsonl`.

To append new runs:

```bash
python3 scripts/archive_perf_history.py
```

The history ledger is `perf_baseline_run_history_v1.jsonl`.
