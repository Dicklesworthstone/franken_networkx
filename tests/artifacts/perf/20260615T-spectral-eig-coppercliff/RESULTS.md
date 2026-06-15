# br-r37-c1-04z53.9109 Results

## Target

Replace `laplacian_spectrum`'s dense `np.linalg.eigvalsh` dependency with a
100% safe-Rust symmetric eigensolver while preserving NetworkX-observable
sorted eigenvalue semantics.

## Baseline

- Public `laplacian_spectrum`, Barabasi-Albert `n=400`, weighted edges.
- Direct timing: FNX median `3.8730417729821056s`, mean
  `3.8402346484013834s`; NetworkX median `3.4959611810045317s`, mean
  `3.6022113195853307s`.
- rch hyperfine, same command: FNX mean `6.19470703086s`, median
  `8.22652396146s`; NetworkX mean `1.4668198582599998s`, median
  `1.45348864046s`.

## Lever

- Added a safe-Rust Householder tridiagonalization plus implicit-shift QL
  eigenvalue solver in `fnx-algorithms`.
- Exposed `_fnx.symmetric_eigvals_rust` for dense symmetric matrices.
- Added a small exact-`Graph` unweighted direct Laplacian builder to avoid SciPy
  sparse materialization on small unweighted cases.
- Routed public `laplacian_spectrum` through the native solver with NumPy
  retained only as a missing-binding/non-convergence fallback.

## Proof

- Spectral golden cases: `2,5,8,32,96`.
- Max absolute delta vs NetworkX: `1.7053025658242404e-13`.
- Max relative delta vs NetworkX: `2.3365857859669603e-14`.
- Tolerance-coded FNX/NX SHA match:
  `cc22d5b3fa648e3216b729ab83a743f39c7242b3df4a840f26c37af5c0847ee9`.
- Raw after payload SHA: `598c286288aeedf5a6c085e36e6de7890e07f4f9e11b245a1b8a73e44a099ff0`.
- Ordering: native solver returns ascending values, matching
  `np.sort(np.linalg.eigvalsh(...))`.
- FP/RNG: no RNG surface; independent solver differs from LAPACK only within
  the explicit spectral tolerance.
- No new native BLAS/LAPACK linkage: `nm -D` and `ldd` found no
  BLAS/LAPACK/OpenBLAS/MKL symbols for `python/franken_networkx/_fnx.abi3.so`.

## After

- Direct timing: FNX median `0.03939812601311132s`, mean
  `0.04006158121628687s`; direct median speedup `98.31x`.
- rch hyperfine: FNX mean `0.60219946488s`, median `0.60331892228s`;
  NetworkX mean `1.51423234748s`, median `1.51490073428s`.
- rch hyperfine mean speedup vs old FNX: `10.29x`.
- After FNX is `2.51x` faster than NetworkX by rch hyperfine mean.

## Validation

- `cargo fmt --package fnx-algorithms --package fnx-python --check`
- `rch exec -- cargo check -p fnx-algorithms --lib`
- `rch exec -- cargo check -p fnx-python --lib --features pyo3/abi3-py310`
- `rch exec -- cargo test -p fnx-algorithms symmetric_eigvals -- --nocapture`
- `rch exec -- cargo test -p fnx-algorithms unweighted_laplacian_spectrum -- --nocapture`
- `rch exec -- cargo clippy -p fnx-algorithms --lib -- -D warnings`
- `rch exec -- cargo clippy -p fnx-python --lib --features pyo3/abi3-py310 -- -D warnings`
- `rch exec -- maturin develop --profile release-perf --features pyo3/abi3-py310`
- Focused pytest:
  `tests/python/test_parity_comprehensive.py -k 'laplacian_spectrum or adjacency_spectrum or normalized_laplacian_spectrum'`
  -> `1 passed, 151 deselected`
- Focused pytest:
  `tests/python/test_review_mode_regression_lock.py -k 'laplacian_spectrum or adjacency_spectrum or normalized_laplacian_spectrum'`
  -> `4 passed, 429 deselected`
- `git diff --check`
- `py_compile` for `python/franken_networkx/__init__.py` and this harness.
- UBS Rust scan completed with the known pre-existing broad inventory and
  false-positive graph-group-id comparison; Python UBS hit the 180s timeout
  without emitting findings.

## Score

Impact `5` x Confidence `4` / Effort `2` = `10.0`; keep.
