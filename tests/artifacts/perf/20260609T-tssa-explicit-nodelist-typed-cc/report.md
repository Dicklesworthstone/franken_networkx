# perf(to_scipy_sparse_array weighted, explicit nodelist): native typed COO

br-r37-c1-pmqhz (residual)

## Problem
The dtype=None weighted to_scipy fast path covered default node order only;
an EXPLICIT (non-default) nodelist with present weights fell back to per-edge
G[u][v] AtlasView Python reads — ~3.5x slower @n=600, ~4.2x @n=1200. Feeds
adjacency_matrix/attr_matrix/etc. when callers pass nodelist.

## Lever (one)
New native `adjacency_nodelist_typed_arrays(g, nodelist, weight, default)`
(Graph + DiGraph): converts each Python node to its canonical key, remaps every
edge's endpoints (storage order -> key -> nodelist position), skips edges with an
endpoint outside a subset nodelist, and tracks `needs_float_dtype` type-based
(matching nx int/float inference). Python routes the explicit-nodelist case to
it. Also fixed a PRE-EXISTING empty-matrix dtype divergence (nx infers float64
from an empty data list; fnx unit/typed paths returned int64) in the unit-weight
and typed branches.

Touched: crates/fnx-python/src/algorithms.rs (new binding + register),
python/franken_networkx/__init__.py (import, routing, empty-dtype fixes).

## Proof (nx-exact, value + dtype)
300 cases: Graph/DiGraph n=1..150, weights int/float/integral-float/absent/None,
default + shuffled + SUBSET nodelist, csr/csc/coo, incl. empty/no-edge graphs.
0 value mismatches AND 0 dtype mismatches vs nx (np.array_equal + .dtype).
2362 matrix-consumer tests pass. FINAL_SHA
6fc0587575d24831b85b126ec347b3740e7ce465124f682b2199d3212c22495a.

## Timing (warm min-of-6, weighted dtype=None, explicit nodelist)
| case          | nx      | before | after |
|---------------|--------:|-------:|------:|
| Graph  n=600  |  4.58ms |  14.79 | 1.96  | (3.5x slower -> 2.3x faster) |
| DiGraph n=600 |  5.63ms |  ~16   | 2.88  |
| Graph  n=1200 | 21.32ms |  73.68 | 9.28  | (4.2x slower -> 2.3x faster) |
| DiGraph n=1200| 24.48ms |  ~73   | 12.81 |

## Score
Impact: high (closes the last weighted-to_scipy gap + a latent dtype bug;
3.5-4.2x slower -> ~2.3x faster). Confidence: high (0/300 value+dtype vs nx,
2362 tests). Effort: moderate. Score >> 2.0.
