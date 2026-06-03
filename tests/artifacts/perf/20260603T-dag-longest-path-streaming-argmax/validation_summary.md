# Validation Summary

- `RCH_ENV_ALLOWLIST=PYTHONPATH rch exec -- env PYTHONPATH=python .venv/bin/python -m py_compile python/franken_networkx/__init__.py tests/artifacts/perf/20260603T-dag-longest-path-streaming-argmax/bench_dag_longest_path.py`: passed.
- `RCH_ENV_ALLOWLIST=PYTHONPATH rch exec -- env PYTHONPATH=python .venv/bin/python -m pytest tests/python/test_dag_extras.py tests/python/test_dag_longest_path_length_port_conformance.py tests/python/test_dag_topology_conformance.py tests/python/test_dag_topology_metamorphic.py tests/python/test_exception_type_parity.py -q -k 'dag_longest_path or dag_longest_cyclic'`: `97 passed, 118 deselected`.
- `ubs tests/artifacts/perf/20260603T-dag-longest-path-streaming-argmax/bench_dag_longest_path.py`: exit `0`; deterministic benchmark RNG noted only as info.
- `timeout 180s ubs python/franken_networkx/__init__.py`: exit `124`; capped with no findings emitted before timeout.
- Golden SHA unique count: `1`.

