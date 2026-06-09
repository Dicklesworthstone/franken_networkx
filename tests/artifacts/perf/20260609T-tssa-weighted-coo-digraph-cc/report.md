# perf(to_scipy_sparse_array weighted dtype=None): native typed COO for DiGraph + any format

br-r37-c1-pmqhz

## Problem
`to_scipy_sparse_array(G, weight="weight", dtype=None)` on graphs with PRESENT
weights took the native typed-COO fast path ONLY for undirected Graph + default
nodelist + csr. DiGraphs and non-csr formats fell back to per-edge G[u][v]
AtlasView Python reads: DiGraph ~3.35x slower than nx, Graph non-csr ~4.21x.
(dtype=None requires type-based int/float inference, which the plain f64 reader
can't reproduce — hence the conservative gate.)

## Lever (one)
Extend the native `adjacency_default_order_typed_arrays` Rust helper to handle
DIRECTED graphs (out-edges via `edges_indexed()`, no symmetric duplication;
storage index == default node order) — it already tracks `needs_float_dtype`
type-based, matching nx. In Python, relax the fast-path gate from
`type(G) is Graph and format == "csr"` to `type(G) in (Graph, DiGraph)` for any
format (the final `matrix.asformat(format)` applies the requested format).

Touched: crates/fnx-python/src/algorithms.rs (typed helper + directed arm),
python/franken_networkx/__init__.py (gate).

## Proof (nx-exact, value + dtype)
120 cases: gnp Graph/DiGraph n=5..150, weights int/float/integral-float/absent,
default + shuffled-explicit nodelist, csr/csc/coo. 0 value mismatches AND
0 dtype mismatches vs nx (np.array_equal + .dtype). Integral-float weights
(2.0) correctly yield float64 (type-based, not value-based). pytest matrix
consumers: 2362 passed. TSSA_SHA captured over 80 outputs.

## Timing (warm min-of-6, N=1000 weighted dtype=None)
| case            | nx     | before | after |
|-----------------|-------:|-------:|------:|
| Graph csc       | 8.70ms |  ~33.9 | 3.10  | (4.2x slower -> 2.8x faster) |
| DiGraph default |12.54ms |  ~37.2 | 4.27  | (3.35x slower -> 2.9x faster) |
| DiGraph csc     |11.67ms |  ~35.8 | 4.40  | (3.3x slower -> 2.6x faster) |

## Score
Impact: high (broad: all weighted-matrix consumers on DiGraphs / non-csr;
3.3-4.2x slower -> 2.6-2.9x faster). Confidence: high (0/120 value+dtype vs nx,
2362 tests). Effort: moderate. Score >> 2.0.

## Residual
Explicit-nodelist (non-default order) weighted dtype=None still uses the Python
fallback (typed helper is default-order only) — lower-frequency; future follow-up.
