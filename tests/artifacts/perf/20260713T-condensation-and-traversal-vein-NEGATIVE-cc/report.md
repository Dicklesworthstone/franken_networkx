# condensation String→int edge scan — REJECT (Amdahl-diluted below null) + String→int traversal vein frontier (cc, 2026-07-13)

Status: **REJECT / REVERTED** for `condensation`; the surrounding String→integer-index BFS/DFS
traversal vein is largely **MINED OUT** for the cc lane after 9 shipped wins this session.

## REJECT: `condensation` cross-SCC edge scan (br-r37-c1-condidx — reverted)

`condensation` probed a String-keyed `node_to_scc: HashMap<&str→usize>` twice per edge (node + succ)
over `successors_iter` while building the cross-SCC edge set. Converted to an index-keyed
`scc_of_idx: Vec<usize>` + `successors_indices` array lookups (byte-identical: same node×successor
scan order, same first-seen (u_scc,v_scc) dedup → identical condensation nodes/edges + identical
returned map). Implemented + measured + REVERTED.

MEASURED (strongly-connected circulant n=30000 deg=20 → ONE SCC, output = (1 node,0 edges) so the
O(|E|) edge scan is the only condensation-specific work), 41 rounds, one binary/one worker:

| row | median | win_rate | p5_p95 |
|-----|-------:|---------:|--------|
| `INDEX_vs_string`      | 1.0426x | 25/41 | [0.8294, 1.3348] |
| `NULL_index_vs_index`  | 1.0158x | 21/41 | [0.7109, 1.3197] |

Candidate median (1.04) sits INSIDE the null spread (null median 1.02, p95 1.32) and candidate p5
(0.83) is far below the null p95 — NOT decidable. **Self-time:** the edge-scan is a small fraction
of `condensation`; the dominant, arm-IDENTICAL floor is (a) the already index-based Tarjan
`strongly_connected_components` pass and (b) the **unavoidable O(|V|) returned
`HashMap<String,usize>` build** (it is part of the public return tuple). Worse, building `scc_of_idx`
ADDS O(|V|) `get_node_index` String hashes, partially offsetting the O(|E|) scan savings. Parity held
+ the bench executed (131s, markers printed), so this is a well-founded reject, not a mis-measure.
LESSON: converting an O(|E|) scan does nothing when the function ALSO pays an unavoidable O(|V|)
String-map build for its RETURN value AND an O(|V|+|E|) shared sub-pass — check the return-type floor
(like [[centrality_to_dict_throwaway_string]] / the transitive_closure output floor) before converting.

## Shipped this session (String→int traversal vein, all byte-identical, all on main)

bipartite_sets 5.63x · shortest_path_unweighted_directed 5.06x · single_source_shortest_path_directed
3.54x · local_node_connectivity_bfs(+directed) 27.6x (O(V²)-amplified via average_node_connectivity) ·
all_shortest_paths(+directed) 9.72x · all_simple_paths_directed 11.5x · single_target_shortest_path
_length_directed 3.31x · single_target_shortest_path_directed 3.69x · transitive_reduction 2.71x.

## Remaining String-keyed traversal residuals — why each is OUT (do not re-mine for a quick win)

- `condensation` — REJECT above (return-map + SCC floor).
- `node_disjoint_paths` (→ all_pairs_node_connectivity) — ALREADY index-based (max-flow node-split over
  `HashMap<(usize,usize)>` + `Vec<HashSet<usize>>` adj). A win here is a HashMap<(usize,usize)>→2D/CSR
  flow rework, NOT a String→int swap, AND `adj` is a `HashSet<usize>` whose iteration order makes the
  returned path composition non-deterministic — off-limits for a byte-exact lever.
- `build_node_split_auxiliary_directed` / `minimum_node_cut_directed*` — max-flow / aux-graph dominated
  (output is a String-keyed nested map / the flow is the cost); setup dedup is Amdahl-drowned.
- `transitive_closure` — REJECTED earlier (2026-07-12, br-r37-c1-tcidx): O(|V|²) closure-edge output
  materialization dominates; needs a DiGraph index-pair edge-extend (separate fnx-classes lever).
- `shortest_path_weighted_directed`, `all_shortest_paths_weighted*` — weighted Dijkstra; float-summation
  / tie-break order risk, and the dijkstra floor is already closed ([[string_key_dijkstra_floor_closed]]).
- `_average_shortest_path_length_undirected` — test-only reference baseline for the bit-parallel aspl.
- `barycenter` — BYPASSED (pyo3 has its own integer-adjacency kernel; the fnx_algorithms fn is dead).
- eccentricity/diameter/distance family — rolled into `distance_measures`, already CSR/bit-parallel.
- all_pairs_shortest_path[_length] — delegate to the (converted) single_source_* cores.

## Net

The clean, byte-exact, production-reached, loop-DOMINATED String→int BFS/DFS surface is effectively
exhausted for the cc lane. What's left is (a) return-type/output-floor-dominated (condensation,
transitive_closure), (b) already index-based (SCC, node_disjoint_paths, distance_measures), (c) float-
order-risky (weighted Dijkstra), or (d) bypassed/test-only. Next productive direction is NOT another
single-BFS swap — it is either the amplified O(V²) helper class (look for scalar-returning `*_bfs`
inside `for i{for j>i{` — mostly done) or a structural change (DiGraph index-pair edge-extend to unlock
transitive_closure/reduction output).
