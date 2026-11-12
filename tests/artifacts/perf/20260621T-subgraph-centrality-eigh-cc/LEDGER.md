# Perf WIN — subgraph_centrality drop native matrix-exp kernel for dense eigh: 0.19-0.69x -> 1.02-1.41x (br-r37-c1-sceigh)

- Agent: `BlackThrush` · 2026-06-21 · File: `__init__.py`
- Same vein as br-r37-c1-katzdense: a native "fast path" that is actually a pessimization
  vs the dense LAPACK routine nx uses.

## The gap
subgraph_centrality routed the (non-normalized, simple-Graph) case to the native
`_fnx.subgraph_centrality_expdiag_rust` kernel (the exp(A) diagonal via matrix-exp). That
kernel is O(n^3) with a large constant and loses badly to LAPACK eigh; the gap GROWS with n:
  native 1.3 / 12 / 91 / 290 ms  vs  eigh 0.8 / 2.8 / 17 / 43 ms  at n=100/200/400/600.
So fnx ran 0.69x @n=100 and 0.19x @n=300 vs nx (which uses dense eigh).

## The fix
Drop the native route; use the dense eigendecomposition path (eigh + sum exp(lambda)*v^2)
for every case. That IS nx's exact algorithm, so the result is BYTE-identical to nx (not
the kernel's prior 8e-15), and faster because fnx's to_numpy_array build beats nx's.

## Verify
- BYTE-IDENTICAL vs nx 800/800 (max abs err 0.00e+00) normalized + non-normalized
  (pytest blocked this turn by an unrelated peer's uncommitted digraph.rs WIP tripping the
  conftest .so-staleness guard; the byte-identical check is the verification here).

## MEASURED (nx/fnx, warm min-20)
| n   | before (native) | after (eigh) |
|-----|-----------------|--------------|
| 100 | 0.69x           | 1.11x (0.85ms) |
| 200 | ~0.4x           | 1.41x (3.03ms) |
| 300 | 0.19x           | 1.02x (7.23ms) |

Loss flipped to a win, byte-identical with nx; the worse-with-n native pessimization is gone.
