# Drop redundant _from_nx_graph double-build in relabel / graph operators

Bead: `br-norebuild`.

## Catastrophe
relabel_nodes, convert_node_labels_to_integers, disjoint_union(_all), compose_all,
union_all and intersection_all built an fnx-typed result graph (R) by iterating the
slow source NodeDataView/EdgeView and per-node/per-edge adds, then ran
`_from_nx_graph(R)` on it -- a SECOND full construction of an already-correct fnx
graph. So these paid ~2x the construction tax. Warm min-of-5 vs networkx:
relabel_nodes 18x, convert_node_labels 17.8x, disjoint_union 20x slower.

## Lever (one)
`_concrete_class_for(G)()` always returns the canonical fnx type, so the rebuilt R
is already an fnx graph with the correct node/edge/adjacency order. Drop the
redundant `_from_nx_graph(R)`: return R directly when it is already an fnx graph;
only convert when R came out as an nx graph (nx-typed inputs). One conceptual
change applied to the shared build-then-rebuild wrappers.

## Isomorphism / golden proof
60 rounds x {relabel (fnx + nx inputs), convert_node_labels (4 orderings),
compose, disjoint_union, union, intersection}, directed + undirected + multigraph:
node order, edge order, FULL adjacency iteration order and node/edge attributes are
byte-identical to networkx. Test (4/4):
tests/python/test_relabel_operator_no_double_build_parity.py.

## Benchmark (gnp p=0.02, warm min-of-5)
    function              before    after
    relabel_nodes         18x       4.29x
    convert_node_labels   17.8x     4.05x
    disjoint_union        20x       5.47x
~4x faster on each. (The residual is the base construction tax of building the
result graph -- substrate-bound. compose/intersection 2-graph variants build
directly / delegate and were not double-builds.)

## Files
- python/franken_networkx/__init__.py: relabel_nodes, compose_all, union_all,
  intersection_all -- drop redundant _from_nx_graph rebuild.
