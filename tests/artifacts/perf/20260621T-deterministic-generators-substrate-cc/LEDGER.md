# SWEEP — deterministic generators: multi-call levers fixed; residual losses are construction-substrate

- Agent: `BlackThrush` · 2026-06-21 · MEASURED · byte-exact

## Fixed (multi-call / multi-add_nodes_from -> one call)
- ladder_graph 0.77x -> 0.79x: 3 add_edges_from -> 1 (chain rails+rungs); byte-exact edges+adj.
- complete_multipartite_graph: per-partition add_nodes_from loop -> ONE attributed add_nodes_from
  (helps the many-partition case: complete_multipartite(50x[2]) 0.81x; turan(200,4) unchanged at
  0.69x — few partitions, dense edges dominate). Byte-exact nodes+subset attr+edges.
(prior turns: circulant_graph 0.72->0.86x, projected_graph 0.37->0.86x — same lever.)

## Dominated this sweep
hypercube 28.4x, lollipop 6.6x, lexicographic_product 3.48x, strong_product 3.19x,
symmetric_difference 1.92x, difference 1.88x, union 1.23x.

## Residual losses — construction-SUBSTRATE bound (not multi-call, not quick wins)
turan_graph 0.69x, star_graph 0.80x, wheel_graph 0.81x, barbell_graph 0.77x, barabasi_albert
0.74x, gnm large 0.92x. All are ALREADY single-bulk-add_edges_from (star/wheel comments confirm);
the gap is the SAME substrate every dense deterministic generator hits: fnx's Rust IndexMap +
PyO3 bulk edge insert is slower than networkx's pure-Python dict per-edge insert for a
construct-once graph. barabasi_albert additionally has a BOUND-BUT-BROKEN native kernel
(_fnx.barabasi_albert_graph: 0/4 byte-exact, 0.02x). The only real lever for this whole class is
a persistent-ordered-dict graph backing (substrate project, bead 4b5ie/9hkgu), not a per-fn fix.
