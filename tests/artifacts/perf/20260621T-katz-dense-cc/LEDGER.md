# Perf WIN — katz_centrality_numpy: revert misguided sparse spsolve to dense, 0.57x -> 1.15-1.30x (br-r37-c1-katzdense)

- Agent: `BlackThrush` · 2026-06-21 · File: `__init__.py`

## The gap
katz_centrality_numpy routed the Katz linear system (I - alpha*A.T)x = b through scipy
`spsolve` (sparse LU) under br-katzsparse, claiming the dense `np.linalg.solve` was "~3.5s
@ n=1200". That premise PREDATED the native-COO `to_numpy_array` fix (374687d39) — the dense
matrix build is now fast. MEASURED: dense BEATS spsolve at EVERY size + density tested:
  n=200..3000, density 0.003..0.5: dense 1.0-633ms vs sparse 2.3-1750ms.
The sparse LU's fill-in overhead always loses on these Katz systems. Net result: fnx
katz_numpy was 0.57x vs nx (which uses dense) on n=300.

## The fix
Use the dense `np.linalg.solve` directly (drop the sparse try/except). This is nx's EXACT
path, so the result is BYTE-identical (not the prior 1e-8), AND faster than nx because the
fnx adjacency build (to_numpy_array) beats nx's.

## Verify
- BYTE-IDENTICAL vs nx 500/500 (max abs err 0.00e+00) across weighted/unweighted/beta-dict/
  alpha (this IS the verification for a pure-Python numerical change). pytest could not run
  this turn — the shared checkout has an unrelated PEER's uncommitted Rust WIP
  (_native_compose in digraph.rs, unbuilt) tripping the conftest .so-staleness guard.

## MEASURED (nx/fnx, warm min-15)
| n   | before (sparse) | after (dense) |
|-----|-----------------|---------------|
| 300 | 0.57x           | 1.30x (1.20ms) |
| 500 | ~0.57x          | 1.18x (3.37ms) |
| 800 | ~0.57x          | 1.15x (11.05ms) |

Loss flipped to a win at all sizes; byte-identical with nx. (For n>~5000 both fnx and nx
are dense O(n^3) — same as nx, no regression; the sparse path never actually won.)
