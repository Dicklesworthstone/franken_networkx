# fix: copy.copy adjacency row-order parity, all four classes (br-r37-c1-o1i86)

## Bug
copy.copy(G) routed through Python _graph_shallowcopy = self.copy(),
which RE-DERIVES adjacency rows (nx.copy() semantics). nx's copy.copy
shares _adj outright, so the copy must show the SOURCE's rows. After
remove+re-add sequences the orders diverge: c:['a','b'] vs nx
['b','a']. The raw Rust __copy__ impls were even worse (unused until
now): they iterated node_key_map (HashMap — scrambled node order) and
replayed edge-iteration order.

## Fix (one lever)
All four Rust __copy__ impls rewritten as WHOLESALE inner clones
(Graph::clone copies IndexMap/IndexSet structures verbatim — node
order, edge order, row content order, multigraph key buckets all
byte-identical to the source), with per-node/per-edge attr dicts as
independent COPIES (fnx's LOCKED copy.copy contract per
test_adj_mapping_parity: structurally equal, mutations do not
propagate — full structural sharing is impossible across Rust storages
and the override pattern caused write-loss, br-r37-c1-4wqn9) and the
adjacency row-key override maps cloned exactly (z6uka). Python
_graph_shallowcopy now routes exact graph types through the captured
raw Rust __copy__; subclasses keep the self.copy() fallback. Graph
attrs stay SHARED via the existing _GRAPH_ATTR_OVERRIDE.

## Proof
- the filed repro (uniform keys, remove+re-add) + the phase-3a
  mixed-key case: rows match nx for all four classes
- 32 random mutation sequences (4 classes x 8 trials, with removals):
  copy.copy canon == nx
- locked-contract suite test_adj_mapping_parity: 4/4 PASS (it failed
  under an intermediate shared-dict version — the lock caught it)
- full pytest on the commit-candidate tree: 21476 passed; remaining
  failures all pre-existing (4 ancient; 2 fixed by a peer's
  uncommitted hunks; 1 newly-surfaced stale edge_py_attrs resurrection
  filed br-r37-c1-kuxuc, reproduced at pre-o1i86 HEAD)
