# Validation Summary

- `RCH_ENV_ALLOWLIST=PYTHONPATH rch exec -- env PYTHONPATH=python .venv/bin/python -m py_compile python/franken_networkx/__init__.py tests/artifacts/perf/20260603T-top-level-adjacency-data-native/bench_top_level_adjacency_data.py`: passed.
- `RCH_ENV_ALLOWLIST=PYTHONPATH rch exec -- env PYTHONPATH=python .venv/bin/python -m pytest tests/python/test_adjacency_data_native_parity.py tests/python/test_io_conversion_parity.py tests/python/test_default_arg_sentinel_parity.py tests/python/test_conversion_extras.py tests/python/test_nx_module_path_parity.py -q -k 'adjacency_data or json_graph'`: 19 passed, 45 deselected.
- `ubs tests/artifacts/perf/20260603T-top-level-adjacency-data-native/bench_top_level_adjacency_data.py`: exit 0; deterministic `random.Random` and proof-harness `assert` reported as info only.
