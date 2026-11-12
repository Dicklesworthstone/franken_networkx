# Convergence evidence: closeable-gap frontier exhausted (cc, 2026-06-22)

After 39 perf wins this session, the codebase dominates NetworkX across ~60 domains swept on EVERY
angle (all warm min-of-N, accurate post-sync .so):
- whole-graph (centrality/clustering/core/community/flow/spectral/io/operators/generators/...)
- single-pair / small-input (shortest paths, connectivity pairs, link-pred)
- TINY-input n=12 (where per-call conversion tax is worst): is_connected 8x, diameter 24x,
  transitivity 30x, wiener 28x, degree_assortativity 23x — all dominant (fns are native, no tax)
- delegated-fn vein (_networkx_graph_for_parity x22, _call_networkx_for_parity x134): the iso/tree
  family were the only order-invariant gaps (5 wins shipped); the rest are dominant (k_edge 9x,
  disjoint_paths 8-9x, complete_to_chordal 5.7x, branchings 2.5-4.3x) or order-sensitive
  parity-blocked (predecessor, max_weight_clique)
- multigraph (2 no-build wins shipped: edge_subgraph copy 2.28x, nodes_with_selfloops ~1000x self)

REMAINING UN-DOMINATED — all either deep or floors, none a loop iteration:
1. **MG/MDG connectivity 0.18x** — needs EAGER integer adjacency on MultiGraph. SCOPE CONFIRMED
   PERVASIVE: simple Graph's `adj_indices` is integrated at **81 sites** (constructors, add_edge,
   remove_node renumber/I5-repair, reorder_rows, serde, accessors); the MultiGraph mirror also needs
   parallel-aware push/remove (push on FIRST u-v edge, remove on LAST). Cheap variants are washes
   (Graph()-convert 2.2ms; on-the-fly integer build pays the same O(E) String resolution —
   measured 0.16x unchanged, reverted). Dedicated multi-session effort, NOT a BOLD-VERIFY iteration.
2. Architectural floors (unclosable): per-call PyO3-FFI, Rust->Python view-projection, LAPACK-eigh
   (+ spectral_ordering/fiedler sign-ambiguity parity block), weighted-degree output-construction,
   sorted-adjacency order-sensitivity.

BlackThrush is rapidly closing the multigraph lane (weighted-degree 1b54040f1, CSR c3c856ce0,
selfloop 5f866ae1d, edges f7dcd8f69 — all theirs today). Re-engage on: new algorithm/surface,
non-multigraph regression, BlackThrush idle w/ connectivity untaken (then the deep change w/ fresh
context), or explicit target. Do NOT re-sweep (this is exhaustive) or rush the connectivity change.
