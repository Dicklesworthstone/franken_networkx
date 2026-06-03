# Validation Summary

## Commands

- `sha256sum -c tests/artifacts/perf/20260603T-ego-graph-empty-edge-pairs/baseline_sha256.txt`
  - Result: passed.
- `sha256sum -c tests/artifacts/perf/20260603T-ego-graph-empty-edge-pairs/after_sha256.txt`
  - Result: passed.
- `env AGENT_NAME=TealSpring rch exec -- env PYTHONPATH=python .venv/bin/python -m py_compile python/franken_networkx/__init__.py`
  - Result: passed. `rch` warned that this is a non-compilation command, but executed it successfully.
- `env AGENT_NAME=TealSpring rch exec -- cargo check -p fnx-python --features pyo3/abi3-py310`
  - Result: passed.
- `env AGENT_NAME=TealSpring rch exec -- env PYTHONPATH=python .venv/bin/python -m pytest tests/python/test_quickwin_rewire_parity.py::test_ego_graph_matches_nx tests/python/test_review_mode_regression_lock.py::test_ego_graph_missing_source_and_nan_radius_match_nx tests/python/test_ego_graph_node_order_parity.py -q`
  - Result: `12 passed in 0.51s`. `rch` warned that this is a non-compilation command, but executed it successfully.
- `timeout 240s ubs --only=python python/franken_networkx/__init__.py`
  - Result: timed out after scanner startup without findings. Existing artifact `ubs_python_init.log` records the scanner startup for this changed file.

## Benchmark Evidence

- Baseline hyperfine: `hyperfine_baseline.json`
- After hyperfine: `hyperfine_after.json`
- Baseline direct sample: `baseline_fnx.jsonl`
- After direct sample: `after_fnx.jsonl`
- Baseline profile: `profile_baseline_fnx.txt`
- After profile: `profile_after_fnx.txt`

## Behavior Evidence

- Golden digest unchanged across NetworkX, baseline fnx, and after fnx:
  - `a66fe1d2d36fe1f69a5966fab6d739d8b5b34ed0aae622b17565fbba8ce603d6`
- Focused parity suite passed through `rch`.
