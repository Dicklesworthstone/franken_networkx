# maximal_matching: integer kernel + native min_maximal_matching / min_edge_dominating_set

Bead: `br-mmnative`.

## Catastrophe
1. The Rust `maximal_matching` kernel built a String-cloned edge list
   (`undirected_edges_in_iteration_order`, 2 heap Strings/edge) and a String-keyed
   `HashSet<String>` matched-node set -- ~1.76x SLOWER than networkx.
2. `approximation.min_maximal_matching` and `approximation.min_edge_dominating_set`
   (both defined by networkx as `maximal_matching(G)`) resolved through the generic
   `_ApproximationNamespace.__getattr__`, which round-trips the graph through an
   O(n^2) fnx->nx conversion -- 15-31x SLOWER than networkx (gap grows with n).

## Lever (one)
Rewrite the kernel to walk the integer adjacency (`neighbors_indices`) and consider
each undirected edge once from its smaller-index endpoint (`u < v`, which also
skips self-loops, as networkx does), in networkx's exact `G.edges()` order and
(smaller, larger) tuple orientation. Add native `min_maximal_matching` /
`min_edge_dominating_set` namespace methods routing to the kernel (no conversion;
`min_edge_dominating_set` keeps nx's empty-graph ValueError).

## Isomorphism / golden proof
150 graphs (incl. self-loops): maximal_matching, min_maximal_matching and
min_edge_dominating_set are TUPLE-identical to networkx; golden sha256 PASS
(9809d27b...). Empty-graph ValueError preserved. Witness fields preserved
(algorithm/complexity/nodes_touched=node_count/edges_scanned=edge_count/queue_peak).
Python test (7/7): tests/python/test_maximal_matching_native_parity.py.

## Benchmark (gnp p=0.01 undirected, warm min-of-5)
    n      maximal_matching          min_maximal_matching
           nx        fnx     ratio   ratio (was ~30x)
    1000   0.74ms    0.10ms  0.13x   0.14x
    2500   3.71ms    0.29ms  0.08x   0.08x
    5000   14.87ms   0.82ms  0.06x   0.04x
maximal_matching: 1.76x SLOWER -> ~18x FASTER. min_maximal_matching /
min_edge_dominating_set: ~30x SLOWER -> ~25x FASTER. Margins grow with n.

## Files
- crates/fnx-algorithms/src/lib.rs: maximal_matching kernel.
- python/franken_networkx/__init__.py: two native namespace methods.
