# Isomorphism Proof

Bead: `br-r37-c1-oymqq`

## Observable Contract

Target API:

```python
franken_networkx.to_scipy_sparse_array(G, weight="weight", dtype=None, format="csr")
```

for simple `Graph` / `DiGraph` native-backed graphs.

The change only introduces an edge-only sync mode for sparse weighted export. It does not alter graph topology, node order, edge order, dtype inference, SciPy construction, or public graph mutation APIs.

## Golden Digest

Benchmark oracle digests serialize sparse matrix shape, row pointer, column indices, and data payload.

Baseline FNX digest:

```text
12d41580d0336461201dbaa08fecc5250eab75162c958f5a91da80875db1ab37
```

After FNX digest:

```text
12d41580d0336461201dbaa08fecc5250eab75162c958f5a91da80875db1ab37
```

NetworkX reference digest on the same graph and export contract also matched the same value in the baseline and after samples.

## Ordering And Tie-Breaking

The lever does not change ordering policy. Sparse export still uses the same node order vector, index lookup, and `adjacency_default_order_typed_arrays` edge walk. The edge-only sync path writes updated edge attributes into the existing Rust graph storage before the same export kernel runs.

There are no algorithmic tie-breakers in this matrix export path beyond graph insertion order and CSR canonicalization. The golden CSR digest covers row pointer order, column order, and data order.

## Floating-Point

The same Python edge attr values are converted into the same internal attr representation before export. No arithmetic, reduction, rounding, or mixed-precision path was introduced. The digest covers the resulting sparse data bytes.

## RNG

No RNG behavior was changed. The benchmark graph generator seed is fixed at `42`, and the optimization does not touch generator code.

## Mutation Semantics

The existing full sync path remains available and is still used when full node/edge attr sync is required. The new path is selected only by `_sync_rust_edge_attrs(G, edge_only=True)` in native weighted sparse export.

A focused parity test mutates an exposed edge attribute dict, confirms the sparse export uses the edge-only sync path, and verifies the resulting CSR payload matches NetworkX:

```text
test_dtype_none_present_string_weight_uses_edge_only_sync
```

The Rust edge-only sync method intentionally does not clear `edges_dirty`, matching the existing conservative dirty-edge behavior for handed-out live edge attr dictionaries.

## Validation

- `rch exec -- cargo check -p fnx-python --features pyo3/abi3-py310`: passed.
- `rch exec -- cargo clippy -p fnx-python --features pyo3/abi3-py310 -- -D warnings`: passed.
- `rustfmt --edition 2024 --check crates/fnx-python/src/lib.rs crates/fnx-python/src/digraph.rs`: passed.
- `.venv/bin/python -m py_compile python/franken_networkx/__init__.py`: passed.
- `rch exec -- .venv/bin/python -m pytest tests/python/test_to_scipy_sparse_native_weighted_parity.py -q`: `297 passed`.
- `rch exec -- .venv/bin/python -m pytest tests/python/test_to_scipy_sparse_default_native_parity.py -q`: `7 passed`.
