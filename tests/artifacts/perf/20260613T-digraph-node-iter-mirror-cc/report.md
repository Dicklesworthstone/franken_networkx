# PyDiGraph incremental node_iter_mirror — list(G) 6.1x / list(G.nodes()) 15.5x → parity

Bead: br-r37-c1 node-iteration substrate (DiGraph leg)
Agent: cc
Date: 2026-06-13

## Problem

The single most common networkx operation — iterating a graph's nodes — was
6-15x slower than nx for DiGraph:

| op                  | fnx before | nx     | before vs nx |
|---------------------|-----------|--------|--------------|
| `list(G)`           | 29.9µs    | 4.87µs | 6.14x slower |
| `list(G.nodes())`   | 75.4µs    | 4.86µs | 15.5x slower |

`PyDiGraph.__iter__` rebuilt a `Vec<PyObject>` of every node's display key per
call (via `cached_node_key_vec`) and wrapped it in a `NodeIterator`;
`DiNodeView.__iter__` (NoData) rebuilt the same Vec into a `DiViewIterator`.
Both were O(V) PyO3 key materialisations per call and returned the wrong
iterator type (not `dict_keyiterator`).

PyGraph already solved this (commit 8b7fb51da) with an **incremental
`node_iter_mirror`** — a live `{node: None}` PyDict kept in insertion order,
mutated in place by every node add/remove/clear hook. `iter(G)` returns its
`dict_keyiterator` directly. The lazy/seq-keyed snapshot alternative was tried
and reverted: it can't reproduce nx's mutation-during-iteration semantics. This
commit gives DiGraph the same incremental mirror.

## Fix

- New `node_iter_mirror: Mutex<Option<Py<PyDict>>>` field on PyDiGraph + four
  helpers (or_init / insert / remove_key / clear), mirroring PyGraph.
- Lazily built from `nodes_ordered()` on first `iter`, then kept live by hooks
  at EVERY node-mutation site: `add_node`, `add_edge` (new endpoints, u-before-v
  nx order), `add_plain_edge_batch`, `add_attr_edge_batch`, `add_attr_node_batch`
  (the `add_edges_from`/`add_nodes_from` bulk fast-paths), `remove_node`,
  `remove_nodes_from`, `clear`. `add_nodes_from`/`add_weighted_edges_from`/
  `update` delegate to the above so are covered transitively.
- `PyDiGraph.__iter__` and `DiNodeView.__iter__` (NoData) now return the
  mirror's `dict_keyiterator`.
- 10 PyDiGraph constructor sites initialise the new field (lazy `None`, so all
  bulk construction paths are captured by the first `or_init`).

## Proof

- Parity sweep: 15 seeds, each applying a random mix of add_node / add_edge
  (incl. brand-new endpoints) / add_edges_from BATCH / remove_node /
  remove_nodes_from, comparing `list(G)`, `list(G.nodes())`,
  `list(G.nodes(data=True))` to nx — **0 mismatches**.
- Iterator type: `iter(G)` and `iter(G.nodes())` are `dict_keyiterator` (== nx).
- Mutation-during-iteration parity: add_node / add_edge-creating-node / BATCH
  add_edges_from / remove_node / clear during iteration ALL raise the exact nx
  `RuntimeError("dictionary changed size during iteration")`. Same-size
  remove+add now matches nx EXACTLY (yields new key, then StopIteration — was a
  divergent custom-guard RuntimeError; regression-lock test updated with proof
  that nx DiGraph yields `2`).
- Golden sha256 of `list(G)` after remove/batch ops:
  `3f1a341dc115476c2764b7ed8c2aedb06caac8b577902a632d88392e69342c24`.
- Full python suite: only the known pre-existing failures remain.

## Timing (1000 nodes, 3000 edges, min-of-6×200)

| op                | before | after  | nx     | after vs nx | self-speedup |
|-------------------|--------|--------|--------|-------------|--------------|
| `list(G)`         | 29.9µs | 4.55µs | 4.59µs | 0.99x       | ~6.6x        |
| `list(G.nodes())` | 75.4µs | 4.84µs | 4.74µs | 1.02x       | ~15.6x       |

Both now at nx parity. MultiGraph/MultiDiGraph have the same gap and the same
fix applies — follow-up commits.
