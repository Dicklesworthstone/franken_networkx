# perf(all_pairs_shortest_path): native BFS-discovery-order binding

br-r37-c1-cfsoi

## Problem
`all_pairs_shortest_path` was 6-10x slower than NetworkX. The Rust kernel
(`fnx_algorithms::all_pairs_shortest_path[_directed]`) collected each
single-source BFS into a `HashMap<String, HashMap<String, Vec<String>>>`,
**destroying BFS-visit order**. To recover nx's inner-dict key order, the
Python wrapper ran a *second full BFS per source* (`_bfs_visit_order`) plus
rebuilt every inner dict — an O(V*(V+E)) pure-Python pass over the whole result.

## Lever (one)
Mirror the already-fast `all_pairs_shortest_path_length` path: build per-source
paths over an **integer adjacency list** in BFS-discovery order natively
(`all_pairs_shortest_path_from_adjacency`), reconstructing each path from a
predecessor array (= nx's `paths[w] = paths[v] + [w]` BFS-tree path). The
binding emits inner dicts already in discovery order, so the Python wrapper
yields them directly — `_bfs_visit_order` removed from the hot path.

Touched: crates/fnx-python/src/algorithms.rs (binding + new helper),
python/franken_networkx/__init__.py (wrapper yields native dicts).

## Proof (behavior unchanged)
47-case golden corpus (random undirected/directed gnp n=2..40, varied cutoff,
path/cycle/star/empty/single/complete). GOLDEN_SHA over full output
(source order + inner dict key order + path lists) is **byte-identical**
before and after:

    1545434da1031e80f47e881bd78339193bbe5c3b20316d25cda5f2f2362ec789

mismatches_vs_nx = 1 before AND after (a pre-existing cycle_graph(7)
adjacency-order divergence: fnx adj[6]=[0,5] vs nx [5,0] — graph construction,
not this function). Same failure set => no behavior change.

pytest tests/python -k "shortest_path or all_pairs or bfs": 1052 passed, 6 skipped.

## Timing (warm min-of-7, watts_strogatz(n,6,0.1))
| n   | nx (ms) | fnx before (ms) | ratio before | fnx after (ms) | ratio after | self-speedup |
|-----|--------:|----------------:|-------------:|---------------:|------------:|-------------:|
| 200 |   ~19   |          154.0  |       10.0x  |          27.1  |      1.42x  |        5.7x  |
| 400 |   ~89   |          639.0  |        8.2x  |         133.1  |      1.49x  |        4.8x  |
| 800 |  ~479   |         2666.4  |        6.1x  |         492.1  |      1.03x  |        5.4x  |
| dir400 | ~77  |             —   |          —   |          94.4  |      1.22x  |          —   |

## Score
Impact: high (fundamental all-pairs op, 4.8-5.7x self-speedup, ~6-10x->~1-1.5x
vs nx). Confidence: high (byte-identical golden sha, 1052 tests pass).
Effort: low-moderate. Score >> 2.0.
