# br-r37-c1-6nzsy Isomorphism Proof

## Behavior Surface

The production change only affects `_should_delegate_dijkstra_to_networkx` for
simple `Graph`/`DiGraph` objects with string weights and a clean edge-attribute
state. It caches the result of the existing native classification scan. It does
not change:

- callable weight delegation
- non-string weight delegation
- multigraph delegation
- NetworkX fallback behavior for negative, non-finite, non-numeric, or `None`
  edge weights
- the native bidirectional Dijkstra kernel
- heap ordering, shared FIFO counter, tie-breaking, path reconstruction, or
  integer-vs-float length coercion

## Invalidation

The cache key is `(weight, nodes_seq, edges_seq)`.

The Rust token also includes `edge_attrs_dirty`. When that flag is true, the
dispatcher does not read or write the cache and falls through to the previous
scan path. This preserves direct live edge dict mutation such as
`G[u][v]["weight"] = "x"`.

## Golden Cases

After golden digest:

`446581281b84c171a2cc1361e193fa82083621f94d663bb90e8d6799493504c0`

All rows matched NetworkX exactly for:

- positive integer weights
- positive float weights
- absent weight attribute
- boolean weights
- negative edge weight
- positive infinity
- NaN
- `None`
- string weight value and TypeError text
- callable weight
- non-string weight argument
- cache populated, then `add_edge(..., weight=-5)`
- cache populated, then live `G[1][2]["weight"] = "x"`

## Validation

- `cargo fmt -p fnx-python --check`
- `rch exec -- cargo check -p fnx-python --features pyo3/abi3-py310 --all-targets`
- `rch exec -- cargo clippy -p fnx-python --features pyo3/abi3-py310 --all-targets -- -D warnings`
- `rch exec -- env PYTHONPATH=python .venv/bin/maturin develop --release --features pyo3/abi3-py310`
- `rch exec -- env PYTHONPATH=python .venv/bin/python -m py_compile python/franken_networkx/__init__.py tests/artifacts/perf/20260605T-dijkstra-weight-prescan-6nzsy/dijkstra_weight_prescan_bench_6nzsy.py`
- `rch exec -- env PYTHONPATH=python .venv/bin/python -m pytest tests/python/test_shortest_path.py::TestShortestPath::test_negative_weight_dijkstra_point_to_point_parity tests/python/test_dijkstra_positive_inf_weight.py tests/python/test_integer_weight_return_type_parity.py -q`
- `ubs crates/fnx-python/src/algorithms.rs tests/artifacts/perf/20260605T-dijkstra-weight-prescan-6nzsy/dijkstra_weight_prescan_bench_6nzsy.py`

Note: full UBS over `python/franken_networkx/__init__.py` did not complete the
Python scan after roughly four minutes and was terminated. The partial log shows
the Rust side completed before the Python scan stalled. The monolithic Python
file was covered by py_compile, focused parity pytest, and golden digest checks.
