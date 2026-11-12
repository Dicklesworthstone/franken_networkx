# adjacency_default default-order native index proof

Bead: `br-r37-c1-jyw9h`

Target: `fnx.adjacency_matrix(Graph)` on deterministic BA(8000,4,seed=12345), default `weight="weight"`, `dtype=None`, `format="csr"`.

Profile-backed hotspot:
- Baseline profile: `profile_baseline_fnx.txt`; five calls spent 0.435 s in `_fnx.adjacency_index_arrays`.
- After profile: `profile_after_fnx.txt`; five calls spend 0.035 s in `_fnx.adjacency_default_order_index_arrays`.

One lever:
- Added `adjacency_default_order_index_arrays` for exact `Graph`, default nodelist, CSR export.
- It walks cached per-node neighbor index slices in node insertion order and avoids Python nodelist canonicalization plus per-edge string lookup.
- All explicit nodelist, DiGraph, MultiGraph, weighted, non-CSR, and fallback routes remain on the previous helpers.

Behavior isomorphism:
- Node ordering is unchanged: the optimized route is gated by `nodelist is None`, so node order is the graph's insertion order, identical to `list(G)`.
- Neighbor/tie ordering is unchanged: `Graph::edges_ordered_borrowed()` groups incident edges by node insertion order and adjacency insertion order; `neighbors_indices(row)` is the same adjacency insertion order with integer keys.
- Self-loop behavior is unchanged: a self-loop appears once in the neighbor index slice, matching the previous `ui != vi` duplicate suppression.
- Weight semantics are unchanged: the helper scans Python-visible `edge_py_attrs` for the requested string weight attr and returns `None` if present, preserving the dtype-inference weighted fallback.
- Floating point is not introduced on this path; unit data remains integer `1` and `dtype=None` produces `int64` unit data as before.
- RNG is not used by the optimized export path; the benchmark graph construction seed is unchanged.

Golden output:
- Baseline fnx digest: `987fb0c41578a61146699304815a73d3c6d70160384e8fb3046d1d0c7b7d13c6`.
- After fnx digest: `987fb0c41578a61146699304815a73d3c6d70160384e8fb3046d1d0c7b7d13c6`.
- NetworkX digest: `987fb0c41578a61146699304815a73d3c6d70160384e8fb3046d1d0c7b7d13c6`.

Benchmarks:
- Sampled fnx mean: 0.10564347999995032 s -> 0.020485541585609706 s.
- Sampled fnx median: 0.09835916950396495 s -> 0.01278198850195622 s.
- Hyperfine process mean: 1.8469658425142856 s -> 0.7459860815942857 s.
- Hyperfine process median: 1.8724418587999998 s -> 0.7383190738800001 s.
- NetworkX sampled mean: 0.03375636483663887 s.

Score:
- Impact 4 x Confidence 5 / Effort 2 = 10.0.
- Verdict: keep.
