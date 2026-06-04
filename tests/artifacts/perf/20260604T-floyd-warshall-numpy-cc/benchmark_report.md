# floyd_warshall — numpy-vectorised Floyd-Warshall, drop delegation to nx's Python triple loop (br-r37-c1-fwnumpy)

## Problem
`networkx.floyd_warshall` is a PURE-PYTHON O(|V|^3) triple loop. fnx delegated to it via
`_call_networkx_for_parity` (a full fnx->nx conversion + nx's Python loop) -> ~0.72x SLOWER
than nx (n=200 weighted: fnx 540ms). The native Rust kernel was abandoned because nx's
`defaultdict`-driven inner-dict key ORDER is algorithm-specific and hard to reproduce.

## Lever (ONE)
Build the all-pairs distance matrix with a NUMPY-vectorised Floyd-Warshall
(`A = min(A, A[:,k,None] + A[k,None,:])` over k) — crushing nx's scalar Python loop — then
format the dict-of-dicts in nx's EXACT `defaultdict` insertion order (replicate nx's init:
int-0 diagonal, edge-neighbours in `G.edges()` order, remaining nodes in `G.nodes()` order).

## Behavior parity (isomorphism proof)
- The numpy min-plus uses the same IEEE-754 float ops as nx's `dist_u[w] + dist_w[v]`, so
  values are bit-identical. Value TYPE matched too: nx preserves int arithmetic, so an
  all-int graph yields int distances and a unit/float graph yields float (verified). Graphs
  MIXING int and float weights (per-pair type would be path-dependent), multigraphs
  (to_numpy_array sums parallels vs nx's min), and callable/non-string weights delegate.
- Sweep: 320 random graphs (n 2..30 x int/float/unit/mixed weights x directed/undirected x
  string keys) + explicit negative-weight digraph, empty, single-node, disconnected,
  self-loop -> **byte-exact (value, int/float type, outer AND inner key order)**, mixed
  correctly delegated. Shipped-wrapper sweep 150/150.
- Golden sha256: `4d179865959d1f22c092754f96ffa40209f8310791f8484c6cd5e2a6aa3cf749`.
- Tests: `pytest -k "floyd or shortest_path or all_pairs"` -> 713 passed.

## Benchmark (warm min-of-5, ms)
| n (gnp weighted) | networkx | fnx before (delegated) | fnx after | after vs nx |
|------------------|----------|------------------------|-----------|-------------|
| 150              | 228      | 226                    | 7.2       | 31.8x       |
| 200              | 540      | ~540                   | 15.1      | **34.5x**   |

Before: ~0.72x (slower than nx). After: 31-34x FASTER, byte-exact.

## Score
Impact: very high (0.72x -> 34x swing on an O(V^3) all-pairs primitive, large absolute ms).
Confidence: high (byte-exact incl value type + key order, 320-case golden, 713 tests).
Effort: low (pure Python + numpy, no Rust/build). → Score >> 2.0.
