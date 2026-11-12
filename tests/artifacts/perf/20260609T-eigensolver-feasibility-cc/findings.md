# Eigensolver feasibility (br-r37-c1-3nzg8) — negative results, 2026-06-09

Goal: would a native safe-Rust symmetric eigensolver close the remaining
LAPACK-bound vs-nx gaps (subgraph_centrality 1.16x; communicability dense)?

## Finding 1 — cyclic Jacobi eigendecomp is 2.7-5x SLOWER than scaling-squaring for matrix_exp
Standalone rustc -O bench (jacobi_vs_scaling_squaring_bench.rs), exp(A) via
cyclic-Jacobi (Q diag(exp λ) Qᵀ) vs the shipped scaling-and-squaring kernel:

    n=120 d=6   dens=0.05  ss 4.16ms  jacobi 18.72ms  ss/jac 0.22x  rel 4e-13
    n=200 d=6   dens=0.03  ss 20.6ms  jacobi 110ms    ss/jac 0.19x  rel 3e-13
    n=120 d=60  dens=0.50  ss 7.12ms  jacobi 19.3ms   ss/jac 0.37x  rel 2e-12
    n=200 d=100 dens=0.50  ss 25.5ms  jacobi 112ms    ss/jac 0.23x  rel 3e-12

Jacobi loses even on DENSE matrices (the case it should win). Parity is fine
(rel ~1e-12) but it is a 2.7-5x LOSS. => Do NOT wire an eigendecomp path into
matrix_exp_symmetric; scaling-squaring (2f37838ae) is already optimal for its
sparse-adjacency consumer (communicability_betweenness). Confirms last session's
[[reference_native_vein_mined_lapack_frontier]] negative result empirically.

## Finding 2 — a NAIVE eigensolver cannot close the spectral gaps either
subgraph_centrality / estrada / fiedler use numpy eigh, which calls OpenBLAS
dsyevd (highly optimized, blocked + SIMD). subgraph_centrality is only ~1.16x
slower (likely to_numpy_array conversion overhead, not the eigh). A naive
Jacobi/QL eigensolver in safe Rust would be SLOWER than OpenBLAS, WIDENING the
gap. => bead 3nzg8 requires a world-class BLOCKED + portable-SIMD symmetric
eigensolver (Householder tridiag with blocked WY updates + SIMD QL, or a
divide-and-conquer dsyevd-equivalent) to beat OpenBLAS — a multi-session R&D
effort, NOT a within-the-hour lever. AND the Python consumers live in the
BoldFalcon-locked __init__.py, so even a fast kernel cannot be wired yet.

## Conclusion / next swing
The remaining vs-nx gaps are dense-OpenBLAS-bound behind a file lock. The honest
next swing is a blocked+SIMD symmetric eigensolver/GEMM that beats OpenBLAS
dsyevd (target: subgraph_centrality 1.16x slower -> faster). This is the alien
artifact to elicit (Strassen/blocked/communication-avoiding + portable SIMD),
not a naive port. Gated on the __init__.py lock for wiring.
