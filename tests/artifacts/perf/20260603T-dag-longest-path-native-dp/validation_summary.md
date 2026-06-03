# Validation Summary

- `RCH_ENV_ALLOWLIST=PYTHONPATH rch exec -- env PYTHONPATH=python .venv/bin/python -m py_compile python/franken_networkx/__init__.py tests/artifacts/perf/20260603T-dag-longest-path-native-dp/bench_dag_longest_path.py`: passed.
- `RCH_ENV_ALLOWLIST=PYTHONPATH rch exec -- env PYTHONPATH=python .venv/bin/python -m pytest tests/python/test_dag_extras.py tests/python/test_dag_longest_path_length_port_conformance.py tests/python/test_dag_topology_conformance.py tests/python/test_dag_topology_metamorphic.py tests/python/test_exception_type_parity.py -q -k 'dag_longest_path or dag_longest_cyclic'`: `97 passed, 117 deselected`.
- `rch exec -- cargo check -p fnx-python --features pyo3/abi3-py310`: passed on worker `vmi1153651`.
- `ubs tests/artifacts/perf/20260603T-dag-longest-path-native-dp/bench_dag_longest_path.py`: exit `0`; no critical or warning findings. Bandit noted deterministic `random.Random`, acceptable for a benchmark fixture.
- `timeout 180s ubs python/franken_networkx/__init__.py`: exit `124`; capped with no findings emitted before timeout.
- Golden SHA unique count: `1`.

