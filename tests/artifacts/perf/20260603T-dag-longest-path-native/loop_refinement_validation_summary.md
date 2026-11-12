# br-r37-c1-85fvl validation summary

## Passed

- `rch exec -- .venv/bin/python -m py_compile python/franken_networkx/__init__.py tests/python/test_dag_extras.py tests/artifacts/perf/20260603T-dag-longest-path-native/bench_dag_longest_path.py`
- `rch exec -- .venv/bin/python -m pytest tests/python/test_dag_extras.py tests/python/test_dag_longest_path_length_port_conformance.py -q -k 'dag_longest_path'`
- `ubs tests/python/test_dag_extras.py tests/artifacts/perf/20260603T-dag-longest-path-native/bench_dag_longest_path.py`

## UBS note

`ubs python/franken_networkx/__init__.py tests/python/test_dag_extras.py tests/artifacts/perf/20260603T-dag-longest-path-native/bench_dag_longest_path.py` did not finish after repeated long polls and was terminated. Partial log shows it stalled during Python scanning of the monolithic `python/franken_networkx/__init__.py`. The smaller touched test/artifact files passed UBS; syntax and focused DAG parity passed for the production file.
