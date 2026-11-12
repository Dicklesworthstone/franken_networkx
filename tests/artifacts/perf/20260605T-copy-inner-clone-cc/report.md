# fix(copy): deterministic node order + bulk inner.clone() (Graph/DiGraph)

## Correctness fix (primary)
PyDiGraph::copy rebuilt the new inner graph by iterating `self.node_key_map`
(a Rust `HashMap`, randomized iteration order) and calling `add_node` per node —
so `list(G.copy().nodes())` came out in HASH order, NOT insertion order,
diverging from `list(G.nodes())` and from networkx (project_copy_node_order).
Replaced with `self.inner.clone()`, which copies the IndexMap/IndexSet/Vec
structures verbatim and preserves node + edge insertion order exactly.

PyGraph::copy already iterated `nodes_ordered()` (deterministic), so its order
was correct; it gets the same `inner.clone()` mechanism for the perf cleanup.

## Mechanism / perf cleanup (secondary)
The old loop rebuilt inner edge-by-edge: `add_edge_with_attrs` (String hashing +
adjacency IndexSet insert + edge_index_endpoints push) PLUS a redundant
`py_dict_to_attr_map` re-parse of the just-copied PyDict, per edge. `inner.clone()`
does this in one bulk Rust copy; only the unavoidable per-edge Python
`PyDict.copy()` remains. Correctness around staleness preserved: `edges_dirty`
is propagated (edge-attr staleness reconciles on the next native sync, same as
the source), and node attrs are refreshed from the authoritative Python dicts
(node-attr mutations aren't tracked by `edges_dirty`).

## Proof
- 11-case exactness + deep-copy ISOLATION test (mutating the copy must not leak
  to the original): 0 mismatches, golden sha e87139d7. Covers directed/
  undirected/empty/string-nodes + post-creation node & edge attr mutations.
- nx node+edge order parity after copy(): PASS (directed + undirected).
- Full Python suite: 21278 passed, 0 failed.

## Perf note (honest)
copy() is bottlenecked by the per-edge PyDict allocation (the construction tax:
even empty-attr copy is ~4x nx because each edge gets a fresh PyDict). That lever
needs lazy attr-dict alloc behind the PyGraph struct (br-r37-c1-blwqo /
w1dm8), which spans TealSpring-locked files. inner.clone() removes the Rust
rebuild overhead (~1.2-1.3x) but does not by itself reach Score>=2.0; the value
here is the node-order correctness fix + simpler/cheaper construction.
