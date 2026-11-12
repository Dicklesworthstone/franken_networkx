# perf: minimum_edge_cut(s,t) — native min-cut partition, no conversion

Bead: br-r37-c1-rguir. minimum_edge_cut delegated everything to nx via the full fnx->nx
conversion (1.2-1.5x slower than nx, growing with n: 80ms vs 55ms at n=2000).

## Lever (ONE)
The LOCAL (s,t) case: nx's minimum_st_edge_cut runs an edmonds-karp max-flow on a
unit-capacity auxiliary and rebuilds the cut-set from the residual partition. fnx's
NATIVE min-cut binding (_minimum_cut_raw) reproduces nx's edmonds-karp residual
byte-for-byte and returns that partition. Force unit capacities via a sentinel
capacity attr that no edge carries (the native flow_edge_capacity defaults missing
to 1.0 — nx ignores edge capacities in minimum_edge_cut too), then rebuild the cut-set
from G's adjacency. No graph conversion; no Python auxiliary construction. The GLOBAL
(no s,t) case and multigraph / explicit flow_func stay delegated (the 5jbv9 tie-break
contract).

## Proof (byte-exact)
- Golden cut-set (exact (u,v) tuples) over 73 graphs (gnm/gnp undirected+directed,
  icosahedral, karate, cycle) x sampled (s,t) pairs == nx for every case:
  f1b951b9682f793dab527112a74dae774e245366061aa9162d78ed8b9a2744f8
- Separately: 141-trial random corpus 0 failures; sentinel forces unit caps even on
  graphs WITH a 'capacity' attr (verified == nx). Error contracts (both-or-neither,
  node-not-in-graph) match nx. 782 connectivity/cut tests pass.

## Benchmark (connected_watts_strogatz, min-of-8)
| n    | nx (ms) | fnx before | fnx after | before vs nx | after vs nx |
|------|---------|------------|-----------|--------------|-------------|
| 800  | 20.6    | ~28 (1.2x) | 5.09      | 1.23x slower | 4.05x FASTER|
| 2000 | 69.1    | ~80 (1.5x) | 15.35     | 1.47x slower | 4.5x FASTER |

1.2-1.5x slower -> 4-4.5x FASTER than nx (~5.3x self-speedup). Byte-exact, pure-Python
(reuses the existing native min-cut binding's unit-cap default + residual partition).
