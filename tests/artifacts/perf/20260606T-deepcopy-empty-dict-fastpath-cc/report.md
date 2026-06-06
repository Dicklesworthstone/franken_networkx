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

## Lever 3 (br-r37-c1-l5ve7): native DiGraph->Graph to_undirected
The DiGraph case had NO native binding — the Python add_edges_from
walk paid ~1.1M interpreter calls on 12k edges (the MultiDiGraph case
had one since earlier work). New PyDiGraph::_native_to_undirected_
deepcopy: u-major succ walk, reciprocal (v,u) MERGES via dict update
(nx add_edges_from semantics, exercised by the (1,2,w=1,a=5)+(2,1,w=2)
pin), first-touch row display objects (forward = succ-row object,
reverse = iteration object), fresh ledger + bulk unrecorded inserts
(added Graph::extend_nodes_with_attrs_unrecorded, mirror of the
DiGraph one). to_undirected: 56.0ms -> 27.3ms = 1.14x vs nx (was
2.92x). Golden sha 7c4264e7 (16 graphs + merge + mixed keys + rows +
mutation independence), full pytest 21774.

## Lever 4 (br-r37-c1-l5ve7): fused native disjoint_union
nx's pipeline = int-relabel G + int-relabel H + union_all — THREE full
Python rebuilds (and fnx paid them all through Python wrappers). New
PyGraph::_native_disjoint_union replicates the composite output in ONE
walk: int node labels/display objects, u-major edge-stream row orders
(the pipeline's stable fixed point), G-then-H graph-attr update,
shallow-copied attr dicts (fresh dicts, shared values — nx
datadict.update semantics). disjoint_union: 152.9ms -> 41.3ms = 0.76x
vs nx (FASTER; was 2.99x slower). Note: a genexpr->list materialization
micro-lever was MEASURED AND REJECTED first (list build cost exceeded
the batch-path win). Golden sha f033b4e0 (16 attr/iso/graph-attr
trials + node types + result mutability), full pytest 21774.

## Lever 5 (br-r37-c1-l5ve7): native compose
PyGraph::_native_compose mirrors nx compose_all per-graph semantics
(graph.update / nodes / edges with H-wins datadict.update merges,
first-insert display objects, H's new neighbors appended to existing
rows) in one native pass with the construction-tax recipe + an
attr-less mirror-lookup fast path. compose: 60.8ms -> 31.2ms = 1.56x
vs nx (was 2.98x). Golden sha 9598fb0d (16 OVERLAPPING-node trials w/
H-wins attr merges, graph attrs, mixed keys, result independence).
Residual analysis: per-edge String pair seen-sets + first-touch
py_node_key/py_adj_key clone_refs; skip needs per-part new-node
tracking (subtle in overlap) — diminishing for this hour, noted.

## Lever 6 (br-r37-c1-l5ve7): union -> native compose + walk optimizations
- union(rename=()) now routes its build through _native_compose after
  the disjointness check (nx union_all == compose_all minus that check,
  statement-identical) and the check itself went native
  (_native_nodes_disjoint: canonical-key walk, 0.06ms vs ~24ms for the
  Python set(G).isdisjoint(H)).
- compose walk optimizations: per-walk edge dedup on (usize, usize)
  index pairs (no String allocs); first-touch row stores SKIPPED when
  the part has no row overrides and both endpoints' display objects
  came from this part (identity makes maybe_store a guaranteed no-op);
  cross-part first-touch via has_edge on G instead of a String-pair
  seen-set.
Interleaved bench (NOISY window — nx itself swung 24-39ms): union
2.57x -> ~1.9x, compose ~1.9x (was 2.98x at family baseline). Golden
sha 0606c2bd (union disjoint+attrs+error+rename, compose overlap
merges, cross-part mixed-key cells), full pytest 21774.
