# quotient_graph edge bucket validation

Passed:

- `rch exec -- maturin develop --release --features pyo3/abi3-py310`
- `rch exec -- .venv/bin/python -m pytest tests/python/test_quotient_graph_default_node_data.py tests/python/test_graph_utilities.py::test_dedensify_and_quotient_graph_match_networkx tests/python/test_graph_utilities.py::test_dedensify_and_quotient_graph_do_not_fallback -q`
- `rch exec -- .venv/bin/python -m pytest tests/python/test_review_mode_regression_lock.py::test_quotient_graph_partition_validation_match_nx tests/python/test_review_mode_regression_lock.py::test_quotient_graph_on_subgraph_view -q`
- `rch exec -- .venv/bin/python -m py_compile python/franken_networkx/__init__.py tests/python/test_quotient_graph_default_node_data.py`
- `rch exec -- cargo check -p fnx-python --features pyo3/abi3-py310`
- `rch exec -- cargo clippy -p fnx-python --features pyo3/abi3-py310 -- -D warnings`
- `ubs --only=python tests/python/test_quotient_graph_default_node_data.py tests/artifacts/perf/20260603T-quotient-edge-bucket/bench_quotient_graph.py`

UBS caveat:

- `ubs --only=python python/franken_networkx/__init__.py tests/python/test_quotient_graph_default_node_data.py tests/artifacts/perf/20260603T-quotient-edge-bucket/bench_quotient_graph.py` timed out after 180s while scanning the large generated `python/franken_networkx/__init__.py`.
- The smaller touched test and harness files completed with 0 critical issues and 0 warnings.

Profile shift:

- Before: `edge_relation`/`has_edge` dominated the default quotient path.
- After: edge-relation scanning is gone from the top profile; default node-data subgraph/density construction is the next profile-backed hotspot.
