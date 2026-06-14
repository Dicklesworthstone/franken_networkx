# bipartite.spectral_bipartivity — two dense expm → one eigendecomposition (~90-100x)

Bead: br-r37-c1-1h238
Agent: cc / 2026-06-14

## Problem

`fnx.bipartite.spectral_bipartivity` was re-exported from networkx
(`@nx._dispatchable`). nx's implementation forms TWO dense matrix exponentials of
the adjacency — `expm(A)` and `expm(-A)` (each an O(n³) Padé approximation over a
dense n×n matrix) — then `coshA = 0.5*(expA+expmA)`. ~430-455ms at n=270; the
single most expensive bipartite metric.

## Fix (spectral identity — eigenvalues replace matrix exponentials)

The adjacency `A` of an undirected graph is symmetric, so `A = V Λ Vᵀ` and
`f(A) = V f(Λ) Vᵀ` for any analytic `f`. Thus:

- **`nodes=None`** (whole graph): the result is
  `trace(cosh A) / trace(exp A) = Σ_i cosh(λ_i) / Σ_i exp(λ_i)` — needs only the
  eigenVALUES. One `np.linalg.eigvalsh(A)`, no matrices exponentiated. (The
  eigvalsh-trace lever: `trace(f(A))` never needs eigenvectors.)
- **`nodes` given** (per node): `expm(A)_ii = Σ_k V_ik² e^{λ_k}` and
  `cosh(A)_ii = Σ_k V_ik² cosh(λ_k)` — one `np.linalg.eigh(A)` then two
  matrix-vector products `(V∘V) @ e^Λ`, `(V∘V) @ cosh Λ`. No dense expm.

This collapses two O(n³) Padé matrix-exponentials into a single symmetric
eigendecomposition. Directed / multigraph / nx-typed inputs delegate to nx
(general non-symmetric `expm`), with a weight-preserving conversion.

## Proof

- 100-case parity sweep (50 seeds × {`nodes=None`, random `nodes` subset},
  weighted and unweighted): result matches nx to the module's **round-6**
  conformance bar — 0 mismatches (actual agreement ≈1e-10, far tighter).
- `path_graph(4)` → 1.0 (fully bipartite); `weight=None` parity.
- Golden (gnmk 40×30/250): fnx `1.0` == nx `1.0`.
- Targeted bipartite conformance + full suite (remote, rebuilt): 22265 passed,
  only the 6 known pre-existing failures.

## Timing (min-of-8, gnmk 150×120/1200)

| op | before (2× dense expm) | after (1 eigendecomp) | ratio |
|----|------------------------|------------------------|-------|
| spectral_bipartivity | 441ms | 4.4ms | **0.010x (~100x)** |

Numerical parity (round-6, the conformance bar). The deeper NO-GAPS follow-up is
a 100%-safe-Rust symmetric eigensolver (Householder tridiagonalization +
implicit-QL, or Jacobi) to replace `np.linalg.eigvalsh`/`eigh` here and unblock
the gated spectral family (fiedler_vector / spectral_ordering, target ~10-30x)
once `__init__.py` is free. Pure-Python (numpy) for now.
