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

## UPDATE (cc): connectivity on-the-fly integer-CSR is a WASH — needs EAGER integer adjacency

ATTEMPTED + REVERTED: rewrote multigraph_connected_components_borrowed to build a Vec<Vec<usize>>
integer adjacency (index_of HashMap + neighbors_iter) then integer-BFS. Built in an isolated
worktree (BlackThrush's concurrent broken digraph.rs WIP — a DegreeKind pyfunction mid-edit —
poisoned the shared-tree build). Parity 0 (component order byte-exact), but perf UNCHANGED (~0.16x).
Root cause: MultiGraph is fully String-keyed (adjacency FxIndexMap<String, IndexMap<String,...>>,
EdgeKey{left:String,right:String} — no integer rows anywhere). Resolving String neighbors -> indices
(index_of[v]) costs O(E) String hashes — the SAME cost as the String-keyed BFS it replaces, just in
a separate build pass. So the integer BFS speedup is cancelled by the String->index build.

The ONLY fix that dominates: add EAGER integer adjacency rows to MultiGraph (mirror simple Graph's
`adj_indices`, maintained by every mutation with the I5 repair pattern) so connectivity reads
integer rows directly with NO String resolution. That is a substantial fnx-classes change (struct
field + all-writers maintenance + clone), in the same family as the int-key cached-flag lever — a
dedicated session, not a loop iteration. Until then MG connected_components/is_connected/
number_connected_components stay ~0.18x (String-BFS floor).
