# perf(single_target_shortest_path): native ordered reverse-BFS, drop pure-Python BFS

br-r37-c1-stsp

## Problem
`single_target_shortest_path` was 4-5x slower than nx (scaling with |V|+|E|).
A native binding existed but was shadowed by a pure-Python reverse-BFS wrapper:
the native kernel collected results into a `HashMap`, losing BFS-discovery key
order (152/178 inner-key-order mismatches vs nx), so the wrapper recomputed the
whole BFS in Python (per-node `predecessors()`/`neighbors()` wrapper calls).

## Lever (one)
Rewrite the native binding to do an ordered reverse-BFS from `target` over
integer adjacency (undirected: `neighbors_iter`; directed: `predecessors_iter`),
recording a successor-toward-target array and emitting `{node: path}` with keys
in BFS-discovery order — matching nx's dict-insertion order. The Python wrapper
now routes straight to it (keeps the NodeNotFound guard + negative-cutoff
coercion). Dead helper `_single_target_shortest_path_neighbors` removed.

Touched: crates/fnx-python/src/algorithms.rs (binding + 2 helpers),
python/franken_networkx/__init__.py (import alias + wrapper + helper removal).

## Proof (behavior unchanged / nx-exact)
1256-case corpus (random undirected/directed gnp n=2..40 x targets x
cutoff{None,1,2,3}): **0 mismatches vs nx** (key order + path lists).
Missing-target raises NodeNotFound (parity preserved).
STSP_SHA 986dfed4fd01e3e98647675e496289eda59c25518e82fd98ddc4def0458bd3da
pytest -k "single_target or shortest_path": 523 passed, 6 skipped.

## Timing (warm min-of-9, watts_strogatz(n,6,0.1), target=0)
| case          | nx (ms) | fnx before | before ratio | fnx after | after ratio |
|---------------|--------:|-----------:|-------------:|----------:|------------:|
| undir n=200   |  0.097  |    ~0.34   |    ~4.96x    |   0.158   |    1.62x    |
| undir n=800   |  0.303  |    ~1.51   |    ~3.96x    |   0.459   |    1.52x    |
| undir n=2000  |  0.805  |    ~3.89   |    ~4.78x    |   1.310   |    1.63x    |
| dir n=2000    |  0.892  |      —     |      —       |   1.427   |    1.60x    |

~3x self-speedup; residual ~1.6x is fixed per-call PyO3 + dict-build overhead.

## Score
Impact: moderate (common BFS primitive, ~3x self-speedup, 4-5x->1.6x vs nx).
Confidence: high (0/1256 vs nx, 523 tests pass). Effort: low. Score >= 2.0.
