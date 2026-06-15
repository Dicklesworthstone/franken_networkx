# br-r37-c1-04z53.9109 spectral eigvals

## Lever

Small exact `Graph` unweighted `laplacian_spectrum` now routes through a native
safe-Rust path:

1. Build dense `D - A` directly from native edge indices.
2. Ignore self-loops in the Laplacian diagonal/off-diagonal contribution, matching
   NetworkX cancellation semantics.
3. Solve eigenvalues with the safe-Rust Householder tridiagonalization plus
   implicit-shift QL kernel.
4. Fall back for directed, multigraph, subclass, weighted, empty, or `n > 32`
   cases.

This removes SciPy sparse materialization and NumPy LAPACK dispatch from the
measured small unweighted path without widening the larger-matrix risk surface.

## Baseline and re-benchmark

Commands were rch-prefixed `hyperfine` runs with 10,000 in-process iterations.

| case | fallback mean | native mean | speedup |
| --- | ---: | ---: | ---: |
| `path32` | 2.42337359018 s | 0.96297563518 s | 2.51654714995x |
| `grid25` | 2.51954494422 s | 0.67624610642 s | 3.72578107334x |

Score: Impact 3.13 (geomean of speedups) x Confidence 0.90 / Effort 1.0 = 2.82.

## Parity

Golden corpus:

- `path8`
- `cycle10`
- `star16`
- `complete20`
- `grid25`
- `path32`
- `selfloop2`
- `weighted_fallback`

Golden SHA256:

```text
a9fa81fbc684c355fc7aed1c029d010c81383d4f3bb0a522418a5d58dc22e2fe
```

Maximum absolute delta vs NetworkX: `1.7763568394002505e-14`.
Maximum relative delta vs NetworkX: `3.5527136788004627e-15`.

## Profile

`path32`, 10,000 loops:

- Native profile: `laplacian_spectrum` cumulative `0.586s`; native Rust
  `unweighted_laplacian_spectrum_rust` cumulative `0.544s`.
- Fallback profile: `laplacian_spectrum` cumulative `2.797s`;
  `laplacian_matrix` cumulative `2.168s`; NumPy eigvalsh path remains in the
  fallback call chain.

## Dependency check

`ldd python/franken_networkx/_fnx*.so | rg -i 'blas|lapack|openblas|mkl'`
returned no matches.

## Validation

- `cargo fmt --package fnx-algorithms --package fnx-python --check`
- `rch exec -- cargo test -p fnx-algorithms symmetric_eigvals --lib`
- `rch exec -- cargo test -p fnx-algorithms unweighted_laplacian_spectrum --lib`
- `rch exec -- cargo check -p fnx-python --lib --features pyo3/abi3-py310`
- `rch exec -- maturin develop --profile release-perf --features pyo3/abi3-py310`
- `.venv/bin/python -m pytest tests/python/test_review_mode_regression_lock.py::test_laplacian_spectrum_native_direct_path_matches_nx -q`
