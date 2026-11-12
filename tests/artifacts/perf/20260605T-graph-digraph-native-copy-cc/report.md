# perf: route Graph/DiGraph.copy() to the native order-preserving clone

The Python `_copy_preserving_insertion_order` wrapper used its native fast path
(`self._native_copy()`) ONLY for MultiGraph/MultiDiGraph; plain Graph/DiGraph
fell to the generic rebuild (`type(self)(); add_nodes_from(self.nodes(data=True));
add_edges_from(self.edges(data=True))`) — ~4-5x slower than nx and bottlenecked on
the edges(data=True) materialization + per-edge add_edges_from.

The native `PyGraph::copy` / `PyDiGraph::copy` already bulk-clone the inner Rust
graph (`inner.clone()` — IndexMap/IndexSet/Vec verbatim: node + edge insertion
order AND public endpoint orientation preserved) and shallow-copy the Python attr
dicts (matching nx's shallow-copy contract). They were just shadowed by the
Python `copy` override at the class level. (The wrapper's "Rust clone path
canonicalizes endpoints" rationale was stale — `inner.clone()` preserves it.)

Lever: expose the native copy as `_native_copy` on PyGraph + PyDiGraph (thin
aliases) and extend the wrapper gate to `type(self) in (Graph, DiGraph,
MultiGraph, MultiDiGraph)` — exact types use the native clone; subclasses /
as_view keep the rebuild.

Proof: copy_parity_proof.py — 1600 cases (Graph + DiGraph x self-loops x attrs)
vs networkx: 0 mismatches on node order, edge order, edge/node/graph attrs;
copy == original; mutating the copy leaves the original unchanged (independence).
Copy/subgraph pytest pass.

Perf (release A/B, n=8000): Graph.copy() 282ms -> 28.6ms = 4.99x self (now 0.91x
vs nx — FASTER than nx, was 4.4x slower). DiGraph.copy() 391ms -> 170ms = 2.75x
self (2.62x vs nx, was ~4x). copy() is a core op (subgraph/relabel/to_directed/
reverse + countless algorithms build on it), so the win compounds project-wide.
