# Isomorphism Proof

Change: weighted sparse export uses `Graph._fnx_sync_edge_attrs_to_inner()` instead of full node+edge sync.

- Ordering preserved: yes. Rows, columns, and data are still emitted by the same `adjacency_default_order_arrays` native helper and SciPy COO-to-CSR conversion.
- Tie-breaking unchanged: yes. No traversal order or duplicate canonicalization logic changed.
- Floating-point unchanged: yes. Edge weight extraction and f64 data emission are unchanged.
- RNG unchanged: yes. Benchmark graph generation still uses fixed NetworkX seed `12345`.
- Node attribute semantics unchanged for other kernels: yes. Full `_fnx_sync_attrs_to_inner()` remains the default helper for existing callers.
- Sparse edge mutation semantics preserved: yes. The edge-only method uses the same `edge_py_attrs` to `inner.replace_edge_attrs` rebuild when `edges_dirty` is set and does not clear the persistent dirty flag.
- Golden digest unchanged: `67df0f0442003e5ba6963b28f9aa88837492b8a9953d9e62550cc3c88ece6a77`.
- Broader sparse sweep: all six sparse cases report `digests_match: true` after the change.
