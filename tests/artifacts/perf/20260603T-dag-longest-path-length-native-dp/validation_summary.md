# Validation Summary

- Baseline FNX direct rch sample: `0.001287505933335827s` per call.
- Candidate FNX direct rch sample: `0.0012375525299770137s` per call.
- Restored FNX direct rch sample: `0.00128257832674232s` per call.
- Hyperfine via rch: `458.0 ms +/- 26.5 ms -> 436.5 ms +/- 26.8 ms`; overlap is too high for a kept lever.
- `RCH_ENV_ALLOWLIST=PYTHONPATH rch exec -- env PYTHONPATH=python .venv/bin/python -m py_compile tests/artifacts/perf/20260603T-dag-longest-path-length-native-dp/bench_dag_longest_path_length.py`: passed.
- `ubs tests/artifacts/perf/20260603T-dag-longest-path-length-native-dp/bench_dag_longest_path_length.py`: exit `0`; deterministic benchmark RNG noted only as info.
- `git diff HEAD -- python/franken_networkx/__init__.py`: empty after restore.

