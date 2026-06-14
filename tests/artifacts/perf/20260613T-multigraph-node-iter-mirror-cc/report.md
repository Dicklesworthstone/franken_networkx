# PyMultiGraph incremental node_iter_mirror — list(G) 6.3x / list(G.nodes()) 8.5x → parity

Bead: br-r37-c1 node-iteration substrate (MultiGraph leg — final type)
Agent: cc
Date: 2026-06-13

## Problem

Last of the four graph types with the node-iteration gap (Graph 8b7fb51da,
DiGraph 1405c3d13, MultiDiGraph 2fa4953ee already done). `iter(G)` /
`list(G.nodes())` rebuilt a `Vec<PyObject>` of every display key per call.

| op                  | before vs nx |
|---------------------|--------------|
| `list(G)`           | 6.32x slower |
| `list(G.nodes())`   | 8.51x slower |

## Fix

Ported the incremental `node_iter_mirror` (live `{node: None}` PyDict, in-place
mutated by hooks, `iter` returns its `dict_keyiterator`) to PyMultiGraph:

- New field + or_init/insert/remove_key/clear helpers.
- Hooks at every node-mutation site: `add_node`, `add_edge` (new endpoints,
  u-before-v) AND its `fast_add_explicit_fresh_int_endpoint_edge` fast path,
  five batch fast-paths (attributed-edge node_entries batch, attributed-node
  batch, three keyed-edge batches), `remove_node`, `remove_nodes_from` (inline),
  `clear`. `add_nodes_from` delegates to `add_node`; `clear_edges` keeps nodes.
- `PyMultiGraph.__iter__` and `MultiGraphNodeView.__iter__` serve the mirror.
- 9 constructor sites init the lazy field.

## Proof

- 15-seed mixed-mutation parity sweep (add_node / add_edge new-endpoint /
  keyed-edge BATCH / attributed-node batch / remove_node / remove_nodes_from)
  vs nx: `list(G)`, `list(G.nodes())`, `list(G.nodes(data=True))` — **0 mismatches**.
- `iter(G)` is `dict_keyiterator` (== nx).
- Mutation-during-iteration parity: add_node / add_edge-new / BATCH / remove /
  clear all raise nx's exact `RuntimeError("dictionary changed size during
  iteration")`. Same-size remove+add now matches nx — the regression-lock test's
  no-raise branch now covers ALL FOUR graph classes.
- Golden sha256 of `list(G)` after remove/batch ops:
  `47f52af2c7521bd9919cdb5e29b35d07806933090e17b6e917e411e0fa11e34f`.
- Full python suite: only the known pre-existing failures remain.

## Timing (1000 nodes, 3000 edges, min-of-6×200)

| op                | before vs nx | after vs nx |
|-------------------|--------------|-------------|
| `list(G)`         | 6.32x        | 1.17x       |
| `list(G.nodes())` | 8.51x        | 0.88x (beats nx) |

All four graph types now at nx parity for node iteration. The incremental
node_iter_mirror substrate is complete across Graph/DiGraph/MultiGraph/MultiDiGraph.
