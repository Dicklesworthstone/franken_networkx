# Isomorphism Proof

Bead: `br-r37-c1-5lpag`

## Change

`Graph` now maintains `edge_index_endpoints`, a storage-order cache of edge
endpoint node indices. `adjacency_default_order_typed_arrays` consumes that
cache and the borrowed edge attr map directly instead of resolving endpoint
strings and re-hashing into the edge map for every coordinate.

## Observable Behavior

- Ordering preserved: yes for the exposed CSR matrix payload. The typed native
  route is only used for default-order `Graph` CSR sparse export. Node row/col
  order remains `list(G)`. The COO construction stream can differ internally,
  but CSR canonicalization produces the same sorted payload; before and after
  CSR digests are identical.
- Tie-breaking unchanged: yes. This path emits sparse matrix coordinates, not
  an algorithmic choice among equal answers. It does not change node insertion
  order, edge attrs, or consumer tie-break policy.
- Floating-point unchanged: yes. Float weights are copied from the same
  `CgseValue::Float` edge attr. Integer weights keep the same exact-f64 range
  guard and dtype metadata. Unsupported bool/string/map weights still return
  `None` and use the Python fallback.
- RNG unchanged: N/A. The benchmark graph seed is unchanged; the implementation
  does not use randomness.
- Self-loops unchanged: yes. The helper emits a single `(u, u)` coordinate for
  self-loops, matching the prior symmetric emission guard.

## Golden Output

Golden CSR digest before:

`12d41580d0336461201dbaa08fecc5250eab75162c958f5a91da80875db1ab37`

Golden CSR digest after:

`12d41580d0336461201dbaa08fecc5250eab75162c958f5a91da80875db1ab37`

Artifact checksum verification:

`sha256sum -c artifact_sha256.txt`: passed.

## Validation

- `rch exec -- cargo check -p fnx-classes`: passed.
- `rch exec -- cargo check -p fnx-python --features pyo3/abi3-py310`: passed.
- `rch exec -- cargo clippy -p fnx-classes --all-targets -- -D warnings`: passed.
- `rch exec -- cargo clippy -p fnx-python --features pyo3/abi3-py310 -- -D warnings`: passed.
- `rustfmt --edition 2024 --check crates/fnx-classes/src/lib.rs crates/fnx-python/src/algorithms.rs`: passed.
- `rch exec -- cargo test -p fnx-classes edge_storage_order_index_iter_tracks_mutations`: passed.
- `rch exec -- .venv/bin/python -m pytest tests/python/test_to_scipy_sparse_native_weighted_parity.py -q`: `296 passed`.
- `rch exec -- .venv/bin/python -m pytest tests/python/test_to_scipy_sparse_default_native_parity.py -q`: `7 passed`.
- `timeout 180s ubs crates/fnx-classes/src/lib.rs crates/fnx-python/src/algorithms.rs`: exit 0, zero critical issues.
