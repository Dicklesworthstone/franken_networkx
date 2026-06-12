# perf+correctness: k_edge_augmentation(k=2) — nx linear-time bridge-augmentation

Bead: br-r37-c1-h5qm1. fnx's k_edge_augmentation used a generic greedy for k>=2 that was
BOTH ~11-54x slower than nx AND suboptimal (≈2x more edges than the minimum) on graphs
that actually need augmentation: it enumerated the O(n^2) edge complement, sorted it, and
re-checked connectivity per candidate. nx's unconstrained k=2 case is the linear-time
bridge-augmentation (minimum cardinality, Eswaran-Tarjan).

## Lever (ONE)
Route the unconstrained case (k==2, avail=None, weight=None) to nx's exact linear-time
``bridge_augmentation`` run IN-PROCESS on the fnx graph (no fnx->nx conversion). Other
k / avail / weighted cases keep the greedy.

## Proof (byte-exact + correctness)
- Golden over 84 graphs (gnm random, tree+chords, path, cycle, complete, the bridge
  fixture) asserts EXACT edge set == nx AND validity (G+aug is 2-edge-connected):
  87b26f9d68e79223b8cfba4a1f6631bf4c065996da6e731dbe49baf29aeb1244
  (the OLD greedy matched nx on only 5/60 random graphs and gave ~2x edges).
- 80-trial random corpus: 0 mismatches vs nx (was 5/60). 462 k_edge/connectivity tests pass.

## Benchmark (tree+chords, min-of-6)
| n   | nx (ms) | fnx OLD greedy | fnx NEW | OLD #edges | NEW #edges (=nx) | NEW vs nx |
|-----|---------|----------------|---------|------------|------------------|-----------|
| 100 | 1.29    | 14.5 (11x)     | 1.71    | 32         | 17               | 1.32x     |
| 400 | 5.20    | 276 (54x)      | 6.69    | 143        | 72               | 1.29x     |

Old greedy 11-54x slower AND ~2x suboptimal -> nx-exact minimum cardinality, 8.7-38x
faster than the old greedy. Residual ~1.3x vs nx = the fnx graph-read tax inside nx's
algorithm (follow-up: native bridge-augmentation). Pure-Python.
