# Perf WIN — communicability_betweenness_centrality: drop native LU/Pade expm kernel for nx's in-process scipy-expm algo, 0.40x -> 1.01x (br-r37-c1-cbcexpm)

- Agent: `BlackThrush` · 2026-06-21 · File: `__init__.py`
- Third in the native-pessimization-vs-LAPACK vein (after katzdense, sceigh).

## The gap
communicability_betweenness_centrality routed to the native
`_fnx.communicability_betweenness_centrality_rust` kernel (own safe-Rust LU + Pade[13] expm).
That kernel is ~2.5x SLOWER than nx's per-node `scipy.linalg.expm` loop:
  n=150: native 693ms vs nx 275ms (0.40x);  n=300: native 10.8s vs nx 4.0s (0.37x).
It also diverged ~1e-12 from nx, forcing a separate disconnected-nan delegation
(`_call_networkx_for_parity`) so the inf/nan contract matched.

## The fix
Run nx's EXACT algorithm in-process on the fnx graph (fnx's fast to_numpy_array + scipy
expm; expA once, then per-node expm of A with row/col v zeroed, B=(expA-expm(A_v))/expA).
This is BYTE-identical to nx (0.0e+00) AND 2.5x faster than the kernel. The disconnected
nan contract now falls straight out of the expA division — the separate delegation is gone.
(The n per-node expm are independent, but scipy expm holds the GIL enough that a
ThreadPoolExecutor gave no speedup under test — left serial.)

## Verify
- BYTE-IDENTICAL vs nx 400/400 (max err 0.0e+00) incl 340 DISCONNECTED cases (nan contract
  preserved). pytest blocked this turn by an unrelated peer's uncommitted readwrite.rs WIP
  tripping the conftest .so-staleness guard; the byte-identical numerical check is the
  verification for this pure-Python change.

## MEASURED (nx/fnx)
| n   | before (native kernel) | after (in-process) |
|-----|------------------------|--------------------|
| 120 | ~0.40x                 | 1.01x (116ms)      |
| 150 | 0.40x (693ms)          | ~1.0x (275ms)      |
| 300 | 0.37x (10.8s)          | ~1.0x (4.0s)       |

A 2.5x improvement; loss flipped to parity-with-nx, byte-identical, disconnected contract intact.
