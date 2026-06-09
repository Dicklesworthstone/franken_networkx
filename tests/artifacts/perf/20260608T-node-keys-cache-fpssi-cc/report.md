# _native_node_keys nodes_seq-keyed tuple cache (br-r37-c1-fpssi)

## Problem
_native_node_keys rebuilt N Python node objects on EVERY call (py_node_key per
node: node_key_map String lookup / fresh-int materialisation). At n=2000 that's
~480us vs nx's set(G) at ~19us (pre-existing dict keys) — non_neighbors directed
was ~16-22x nx.

## Lever (ONE)
Cache the built Python tuple of node display objects on the graph, keyed by the
existing nodes_seq mutation counter (std::sync::Mutex<Option<(u64, Py<PyTuple>)>>).
A warm call (node set unchanged) returns the cached tuple in O(1); the first call
after any node add/remove rebuilds + recaches. Invalidation rides the nodes_seq
invariant already trusted by NodeIteratorGuard, so a stale tuple is impossible
without also breaking iteration.

## Proof
- Correctness: warm returns same tuple identity; invalidates on add_node,
  remove_node, implicit-add via add_edge/add_edges_from, remove_nodes_from,
  clear, add-after-clear; copy() has an independent (empty) cache. 0 fails over
  4 classes x all paths. non_neighbors parity 0/360 (4 classes).
- Full test suite: 5227 passed (1 unrelated pre-existing doc-currency failure:
  docs/coverage.md stale from earlier de-delegation commits — regenerated
  separately).
- Speedup (n=2000, x50, min-of-9):
  - _native_node_keys: cold ~480us -> warm 0us (O(1) cached tuple)
  - DiGraph non_neighbors warm: 16x nx -> 1.64x nx
  - MultiDiGraph non_neighbors warm: 22x nx -> 2.00x nx

Closes the bulk of the vs-nx gap for repeated-call patterns (non_edges,
per-node non_neighbors). Residual ~1.6-2x is now the per-call set-difference, not
node-key construction.
