# Perf win — int-LABEL attributed edge batch (br-r37-c1-dodattrbatch, scrambled-int)

- Agent: `BlackThrush` · 2026-06-20 · worktree at origin/main `fc540fbe5`
- File: `crates/fnx-python/src/lib.rs` (reuses the extend method shipped in fc540fbe5)

## Root cause

The exact-index attributed batch (fc540fbe5) only fires when node LABEL == INDEX
(contiguous-int prefix in order). A graph from `to_dict_of_dicts`/`add_nodes_from`
of a NON-0..n-ordered int source (label != index) still fell to the slow String
batch: shuffled-int-node attr `add_edges_from` measured 0.63x nx.

## Lever

`collect_existing_int_label_attr_edge_indices` builds an int-label -> index map
ONCE from the existing nodes (one int hash per endpoint vs String hashing), then
reuses `extend_existing_index_edges_with_attrs_unrecorded`. Bails (slow-path
fallback) on any non-int node, a new endpoint not already present, or a non-3-tuple.

## Win vs NetworkX 3.6.1 (clean worktree, warm min-of-20, 1500n/3000e)

| attr add_edges_from after pre-added int nodes | before | after |
| --- | ---: | ---: |
| nodes IN ORDER (label==index) | (index path) | 1.92x |
| nodes SHUFFLED (label!=index) | 0.63x | **1.42x** (2.52ms -> 1.14ms) |

## Parity

1500 random Graphs: scrambled-int nodes, edges referencing NEW (not-pre-added)
nodes [bail path], empty attrs, duplicate edges [merge] — 0 mismatches (node
order, edges+data, adj row order). pytest -k 'add_edge or from_dict or convert or
construct' 1001 passed (lone failure is the pre-existing fnx.Graph RCM test).
