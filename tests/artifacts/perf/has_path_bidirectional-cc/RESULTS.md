# has_path (undirected) — bidirectional BFS with reused frontier buffers

## Lever
`has_path_fast` did single-source BFS that only noticed the target when POPPED,
exploring the whole forward reachable set / O(|E|) edges before reporting
reachability. Replaced with integer-index **bidirectional BFS** (expand the
smaller frontier, stop the instant frontiers meet) + **reused frontier buffers**
(std::mem::swap into one scratch Vec — no per-level heap allocation).

## Correctness (golden sha256)
1600 (source,target) comparisons across gnp/path/ba/complete/disconnected graphs,
fnx vs networkx: **0 mismatches**.
golden sha256 = 4b1401a86e6614a857382c1550d14c3d274a05e6e353e0f9a25c0b55c5cf23e0
(identical before and after the buffer-reuse refinement)
pytest tests/python -k "has_path or path": 3021 passed, 7 skipped.

## Benchmark (warm min, us/call) — fnx vs nx ratio = nx/fnx
| case                  | nx     | HEAD-fnx     | new fnx       | self-speedup |
|-----------------------|--------|--------------|---------------|--------------|
| dense complete801 nbr | 7.3    | 4.46 (1.6x)  | 1.39 (5.3x)   | 3.2x         |
| path2000 far 0->1999  | 780    | 10.5 (76x)   | 10.76 (72x)   | parity       |
| gnp1000 p=.01         | 21     | 9.05 (2.2x)  | 2.10 (9.9x)   | 4.3x         |
| disconnected 0->1500  | 374    | 5.9 (63x)    | 6.15 (61x)    | parity       |

Note: the FIRST bidirectional cut (fresh `next` Vec per level) regressed
path2000 (33.5us) and disconnected (17.7us) ~3x; the buffer-reuse swap fixes
both back to parity while keeping the dense/sparse-reachable wins.
