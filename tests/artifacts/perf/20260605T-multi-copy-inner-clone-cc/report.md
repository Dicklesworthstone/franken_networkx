# fix(copy): deterministic node order in MultiGraph/MultiDiGraph copy() (br-r37-c1-6xe9c)

## Correctness fix
PyMultiGraph::copy and PyMultiDiGraph::copy rebuilt the new inner graph by
iterating `self.node_key_map` (a Rust HashMap with randomized iteration order)
and calling add_node per node — so `list(G.copy().nodes())` came out in HASH
order, non-deterministic and diverging from `list(G.nodes())` and from networkx
(project_copy_node_order). Sibling of e8fac5a78 (Graph/DiGraph). Replaced with
`self.inner.clone()`, which copies the IndexMap/IndexSet/Vec structures verbatim
and preserves node + edge + parallel-key insertion order EXACTLY.

## Mechanism
Bulk `inner.clone()` replaces the per-edge `add_edge_with_key_and_attrs` (String
hashing + adjacency insert) + redundant `py_dict_to_attr_map` re-parse. Only the
deep-copy of Python attr dicts + per-edge Python key objects (edge_py_keys,
preserving first-wins identity) remains. Staleness preserved: edges_dirty
propagated; node attrs refreshed from authoritative Python dicts (untracked by
edges_dirty).

## Proof
8-case exactness + deep-copy ISOLATION (mutate copy incl. adding a parallel
edge, must not leak to original) + nx node/edge/key order parity, 0 mismatches.
golden sha 99977034. Covers MultiGraph + MultiDiGraph, parallel edges, custom
explicit keys, post-creation node & edge attr mutations, empty graphs.
Full Python suite: see suite log.

## Perf note (honest)
Like e8fac5a78, this is primarily a CORRECTNESS fix (deterministic copy node
order). copy() remains bottlenecked by the per-edge PyDict allocation
(construction tax — the Score>=2.0 lever is lazy attr-dict alloc behind the
locked PyGraph struct, br-r37-c1-blwqo). inner.clone() removes the Rust rebuild.
