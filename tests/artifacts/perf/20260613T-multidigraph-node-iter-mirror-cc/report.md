# PyMultiDiGraph incremental node_iter_mirror — list(G) 4.9x / list(G.nodes()) 9.2x → parity

Bead: br-r37-c1 node-iteration substrate (MultiDiGraph leg)
Agent: cc
Date: 2026-06-13

## Problem

Same gap as the Graph (8b7fb51da) and DiGraph (1405c3d13) legs: iterating a
MultiDiGraph's nodes rebuilt a `Vec<PyObject>` of every display key per call.

| op                  | before vs nx |
|---------------------|--------------|
| `list(G)`           | 4.91x slower |
| `list(G.nodes())`   | 9.18x slower |

## Fix

Ported the incremental `node_iter_mirror` (live `{node: None}` PyDict, in-place
mutated by hooks, `iter` returns its `dict_keyiterator`) to PyMultiDiGraph:

- New `node_iter_mirror` field + or_init/insert/remove_key/clear helpers.
- Hooks at every node-mutation site: `add_node`, `add_edge` (new endpoints,
  u-before-v nx order), the three keyed-edge batch fast-paths
  (`_try_add_edges_from_batch`, `_native_add_keyed_edges_no_data`, the
  attributed-edge batch) + the attributed-node batch (`add_attr_node_batch`),
  `remove_node`, `remove_nodes_from`, `clear`. `add_nodes_from` delegates to
  `add_node`; `clear_edges` keeps nodes so is untouched.
- `PyMultiDiGraph.__iter__` and `MultiDiGraphNodeView.__iter__` serve the mirror.
- 11 constructor sites init the lazy field.

## Proof

- 15-seed mixed-mutation parity sweep (add_node / add_edge new-endpoint /
  keyed-edge BATCH / attributed-node batch / remove_node / remove_nodes_from)
  vs nx: `list(G)`, `list(G.nodes())`, `list(G.nodes(data=True))` — **0 mismatches**.
- `iter(G)` is `dict_keyiterator` (== nx).
- Mutation-during-iteration parity: add_node / add_edge-new / keyed BATCH /
  remove / clear all raise nx's exact `RuntimeError("dictionary changed size
  during iteration")`. Same-size remove+add now matches nx (no raise) — the
  regression-lock test's no-raise branch now includes MultiDiGraph (MultiGraph
  still on the snapshot iterator → follow-up).
- Golden sha256 of `list(G)` after remove/batch ops:
  `47f52af2c7521bd9919cdb5e29b35d07806933090e17b6e917e411e0fa11e34f`.
- Full python suite: only the known pre-existing failures remain.

## Timing (1000 nodes, 3000 edges, min-of-6×200)

| op                | before vs nx | after vs nx |
|-------------------|--------------|-------------|
| `list(G)`         | 4.91x        | 1.09x       |
| `list(G.nodes())` | 9.18x        | 1.03x       |

Both at nx parity. MultiGraph (lib.rs) remains — same fix, next commit (it has
~5 batch new-node sites + the same same-size-mutation nx-divergence).
