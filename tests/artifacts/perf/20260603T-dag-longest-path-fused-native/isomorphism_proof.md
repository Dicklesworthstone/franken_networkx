# Isomorphism Proof

## Change
`br-r37-c1-vij0v` adds `_native_dag_topo_pred_data_key` for exact `DiGraph` and routes `_dag_longest_path_digraph_native` through that fused topo/predecessor snapshot when available.

## Proof Obligations
- Ordering preserved: yes. The native Kahn queue is seeded in `nodes_ordered()` order and drains successors in native successor insertion order, matching the existing `topological_sort` fast path.
- Tie-breaking unchanged: yes. Predecessor groups are emitted target-major in predecessor insertion order, and Python DP still uses strict `>` so first-maximum behavior matches `max(..., key=...)`.
- Floating-point behavior unchanged: yes. Rust only fetches Python edge values; all additions, comparisons, NaN behavior, and TypeError behavior remain in Python.
- RNG unchanged: yes. The benchmark seed only constructs the deterministic DAG; the implementation has no RNG path.
- Error behavior unchanged: yes. Cycles raise `NetworkXUnfeasible`; undirected graphs, multigraphs, views/subclasses, and explicit `topo_order` stay on the existing paths.
- Golden output: baseline FNX, NetworkX, after FNX, and after NetworkX payload SHA all stayed `76214d0b33d25b721eb1437d081b03fcf320e749ed72ceb521a87215d5ebbb7f`.

## Verification
- `sha256sum -c artifact_sha256.txt`: passed.
- Focused DAG parity after fresh rebuild: `97 passed, 119 deselected`.
- Additional regression: `test_native_fast_path_preserves_python_weight_type_error` locks present-`None` weight TypeError parity.
