# perf: deepcopy_py_dict empty-dict fast path (copy family)

## Baseline (warm min-of-7, 12k-edge / 3k-node graphs)
to_directed 119.5ms (3.02x nx) — cProfile: 100% inside
_native_to_directed_deepcopy; dominant cost = one Python copy.deepcopy
interpreter round-trip PER NODE/EDGE on the (empty) attr-mirror dicts.

## Lever (ONE)
deepcopy_py_dict: bound.is_empty() -> fresh PyDict (semantically
identical — deepcopy({}) == {}, memo irrelevant for empty); 16 call
sites across lib.rs/digraph.rs benefit.

## After
to_directed 81.3ms (2.41x) = 1.47x self-speedup; attr-ful dicts still
deep-copied independently (mutation-independence pinned in test).

## Proof
24-graph golden battery (attr-less + attr-ful alternating, to_directed
+ round-trip to_undirected) vs nx, 0 failures; full pytest 21774
passed.

## Residual (beaded)
to_directed 2.41x = per-edge RECORDED add_edge_with_attrs (ledger
record per edge — the known ~5x construction-tax class) +
py_dict_to_attr_map; to_undirected/union/compose/disjoint_union
(~2.8-3.1x) have their own non-deepcopy_py_dict paths.

## Lever 2 (br-r37-c1-l5ve7): bulk unrecorded + fresh ledger
PyGraph::_native_to_directed_deepcopy: per-node/edge RECORDED add_*
(ledger record each) -> extend_nodes_with_attrs_unrecorded +
extend_edges_with_attrs_unrecorded (identical structural insert
sequence, unrecorded); runtime_policy().clone() (deep-copies the
unbounded decision ledger — 7dpyg class) -> RuntimePolicy::new(mode).
to_directed: 81.3ms -> 19.1ms = 0.53x vs nx (~2x FASTER; was 3.02x
slower at baseline). Golden battery sha 7d49a488 (16 graphs,
attrs/isolates/pred-rows/mixed-keys/mutation-independence), 0
failures; full pytest 21774. Recipe proven — remaining family members
(to_undirected 3.1x, union 2.8x, compose 2.8x, disjoint_union 3.1x)
stay on the bead.
