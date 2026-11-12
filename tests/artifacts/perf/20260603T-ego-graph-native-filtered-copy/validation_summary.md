# Validation Summary

## Commands

- `rch exec -- cargo check -p fnx-python --features pyo3/abi3-py310`
  - Result: passed after resolving the candidate compile issue.
- `rch exec -- maturin develop --release --features pyo3/abi3-py310`
  - Result: passed; installed the candidate extension for measurement.
- `rch exec -- env PYTHONPATH=python .venv/bin/python -m py_compile python/franken_networkx/__init__.py tests/python/test_ego_graph_node_order_parity.py`
  - Result: passed.
- `rch exec -- env PYTHONPATH=python .venv/bin/python -m pytest tests/python/test_quickwin_rewire_parity.py::test_ego_graph_matches_nx tests/python/test_review_mode_regression_lock.py::test_ego_graph_missing_source_and_nan_radius_match_nx tests/python/test_ego_graph_node_order_parity.py -q`
  - Result: `14 passed in 0.51s`.

## Performance Gate

- Baseline direct mean: `0.03052246606287857s`
- Candidate direct mean: `0.03164971126631523s`
- Baseline hyperfine mean: `0.6168774760771429s`
- Candidate hyperfine mean: `0.6682278137428571s`

The candidate failed the keep gate and was removed.

## Source Revert Proof

After manual removal, a fresh-index diff against `HEAD` for the candidate source and test surface was empty:

- `crates/fnx-python/src/lib.rs`
- `python/franken_networkx/__init__.py`
- `tests/python/test_ego_graph_node_order_parity.py`
