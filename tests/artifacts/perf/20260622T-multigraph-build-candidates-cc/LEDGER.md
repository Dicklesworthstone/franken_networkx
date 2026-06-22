# Multigraph un-dominated gaps needing a Rust build (cc, findings for a dedicated session)

Found by sweeping the multigraph domain (warm min-of-N). Two no-build wins already shipped from
this sweep: edge_subgraph().copy() (f8345d4a9) + nodes_with_selfloops (108b67be8). The remaining
gaps need native-kernel work (build) and are recorded here rather than rushed:

1. **MG/MDG connected_components / is_connected — 0.34x whole, scales with parallel edges.**
   Measured: high-parallel multigraph (6000 edges, 250 nodes) 0.17x; low-parallel (1500 edges)
   0.86x. ROOT CAUSE: the native `connected_components` (crates/fnx-algorithms/src/lib.rs:2543)
   BFS iterates every PARALLEL edge; nx's BFS walks `G.adj[n]` (unique neighbor dict keys) so it is
   O(unique edges). FIX: dedup neighbors in the multigraph adjacency/CSR before the BFS (multiplicity
   is irrelevant to reachability). Potentially DOMINANT (simple-graph connectivity already is).
   File is TealSpring's (fnx-algorithms); last-active 2026-06-21 (likely stranded) -> takeable.

2. **MDG in_degree(weight) 0.09x / out_degree(weight) 0.13x.** Directional weighted multi-degree
   uses the slow per-node `degree(G,node,weight)` Python path. `_native_weighted_degree` exists but
   is TOTAL (in+out) only. A directional native kernel would help BUT total weighted degree is
   itself only 0.71x (output-construction floor: per-node PyFloat + node-key PyObject build, nx-order
   Neumaier sum). So directional would also land ~0.71x — a big improvement (8-14x self) but NOT
   dominant. Ship only if the 0.71x floor itself can be lifted.

3. **MDG pagerank 0.70x** — likely tied to the same weighted out-degree floor.

Architectural floors (NOT closeable): per-call FFI, Rust->Python view-projection, LAPACK-eigh,
sorted-adjacency order-sensitivity. See project_perf_convergence_floor_taxonomy memory.
