# Perf win — DiGraph existing-nodes attributed batch (br-r37-c1-dodattrbatch)

- Agent: `BlackThrush` · 2026-06-20 · worktree at origin/main `e5865bc52`
- Files: `crates/fnx-classes/src/digraph.rs` + `crates/fnx-python/src/digraph.rs`

Ported the existing-nodes attributed batch (shipped for Graph in fc540fbe5/e5865bc52)
to PyDiGraph — the simple DiGraph inner is already integer-CSR (succ/pred index
rows), so the directed inner gained `extend_existing_index_edges_with_attrs_unrecorded`
(insert by index, duplicates merge last-wins, no String hashing), and PyDiGraph
gained the int-label collect + dispatcher (resolve int endpoints via a one-time
int-label->index map), wired after the fresh path in try_add_attr_edge_batch.

## Wins vs NetworkX 3.6.1 (clean worktree, warm min-of-20, 1500n)

| | before | after |
| --- | ---: | ---: |
| DiGraph attr add_edges_from-after-(shuffled int)-nodes | 0.44x | **1.26x** |
| convert_node_labels_to_integers (DiGraph) | 0.58x | **1.23x** |

## Parity

1500 random DiGraphs: scrambled-int nodes, new-node bail, empty attrs, duplicate
edges (directed merge) — 0 mismatches (node order, edges+data, succ AND pred row
order); convert_node_labels parity True; pytest -k 'digraph or add_edge or relabel
or convert_node or from_dict' 4528 passed.
