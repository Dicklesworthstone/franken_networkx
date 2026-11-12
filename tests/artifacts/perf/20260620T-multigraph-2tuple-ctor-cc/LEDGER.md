# Perf win — MultiGraph 2-tuple constructor batch path (br-r37-c1-ctor2tuple)

- Agent: `BlackThrush` · 2026-06-20 · isolated worktree at origin/main `41ba2c307`
- File: `crates/fnx-python/src/lib.rs` (PyMultiGraph; NOT reserved — only
  `fnx-classes/src/lib.rs` was held by a peer)

Sibling of the MultiDiGraph fix (41ba2c307). `MultiGraph([(u,v),...])` from a bare
2-tuple edge list bailed from `try_absorb_exact_int_str_keyed_ctor_edges` (3/4-tuple
only) to the per-edge add_edge loop. Extended to accept 2-tuples as auto integer-key
edges, with the key counter on the UNORDERED (min,max) pair (undirected); lazy
attr/key objects. 3/4-tuple semantics unchanged.

## Win vs NetworkX 3.6.1 (clean worktree, warm min-of-20, 1500n/7000e)

| MultiGraph(2-tuple edge list) | before | after |
| --- | ---: | ---: |
| | 0.65x | **1.25x** (15.65ms -> 8.25ms) |

Parity: 1500 random MultiGraphs from a 2/3/4-tuple mix incl parallels + self-loops,
0 mismatches (node order, edges keys+data, adj row order). pytest -k multigraph:
2140 passed, 0 fail.

## Still open
Graph ctor 0.73x already batches 2-tuples (`try_add_plain_edge_batch`) — residual is
the batch internals + `__init__` `validate_ctor_edge_list` (in reserved `__init__.py`).
