# Perf — from_dict_of_dicts symmetric-reverse dedup (br-r37-c1-dodsymdedup)

- Agent: `BlackThrush` · 2026-06-20 · isolated worktree at origin/main `1a3af57f6`
- File: `python/franken_networkx/__init__.py` (free — no reservations)

## Root cause (two parts)

1. An UNDIRECTED dict-of-dicts lists every edge TWICE (u->v and v->u); the
   `type(graph) is Graph` branch fed all 2*E triples to add_edges_from.
2. `from_dict_of_dicts` calls `add_nodes_from(d)` BEFORE add_edges_from, which
   DEFEATS the fresh attributed-batch fast path (`try_add_fresh_exact_int_attr_edge_batch`
   gates on `node_count == 0`). So the 2*E triples hit the ~4x-slower general
   attributed batch: clean-measured fnx add_edges_from(7000 attr) on a FRESH graph
   is 1.83x WIN (2.0ms), but the same on a graph-with-nodes is ~7.6ms.

## Lever shipped (part 1 — dedup)

Skip the symmetric reverse (identity-checked `d[v][u] is d[u][v]`, the
to_dict_of_dicts case), halving the batch. Asymmetric reverses are still emitted
so the later one wins exactly as nx's add_edges_from does.

| from_dict_of_dicts (1500n/7000e undirected) | before | after |
| --- | ---: | ---: |
| | 0.58x | **0.74x** (13.76ms -> 9.97ms, ~1.4x self) |

Parity: 800 random Graphs incl self-loops 0 mismatches (node order, adj row order,
edges+data); asymmetric-attrs input matches nx last-wins. pytest -k 'from_dict or
dict_of_dicts or to_dict or node_link': 291 passed.

## Residual (part 2 — NOT yet a win, characterized for follow-up)

Still 0.74x because the deduped E edges hit the slow general attributed batch (the
graph already has nodes). The full win needs an EXISTING-NODES attributed batch
fast path (attributed sibling of `try_add_existing_exact_int_edge_index_batch` in
crates/fnx-python/src/lib.rs) — or relaxing the fresh-attr-batch gate to allow
edge-less pre-existing nodes (the collect must then reuse existing node indices
instead of assigning fresh ones). Both files are now unreserved.
