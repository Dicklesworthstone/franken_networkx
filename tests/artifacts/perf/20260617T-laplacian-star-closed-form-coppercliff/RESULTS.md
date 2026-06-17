# br-r37-c1-04z53.9133 Results

Target:

```python
fnx.laplacian_spectrum(fnx.star_graph(798))
```

## Baseline

- Direct FNX median: `0.212556050974s`
- Direct NetworkX median: `0.031995131983s`
- FNX / NetworkX direct ratio: `6.643x` slower
- Hyperfine FNX mean, five calls/process: `1.429784041600s`
- Hyperfine NetworkX mean, five calls/process: `0.537144778600s`
- Profile: `_fnx.symmetric_eigvals_rust` consumed `1.076s / 1.113s` over five calls.

## Change

Exact unweighted simple star graphs now bypass dense Laplacian construction and eigensolver routing. The wrapper emits the analytic Laplacian spectrum:

```text
[0, 1 repeated n-2, n]
```

Fallback stays on the existing path for weighted edges under a string weight key, non-star degree patterns, empty graphs, directed graphs, multigraphs, subclasses, and unsupported weight arguments.

## After

- Direct FNX median: `0.001328488055s`
- Direct speedup vs baseline: `160.00x`
- Hyperfine FNX mean, five calls/process: `0.329359269020s`
- Hyperfine speedup vs baseline: `4.34x`
- After target profile over 1000 calls contains no dense Laplacian construction or `_fnx.symmetric_eigvals_rust` frame.
- FNX is now `2.03x` faster than NetworkX in the local process-level hyperfine target.

## Isomorphism Proof

- Ordering preserved: `laplacian_spectrum` returns ascending sorted eigenvalues, and the closed form is ascending.
- Tie-breaking unchanged: eigenvalues only; repeated `1.0` values have no eigenvector pairing.
- Floating-point contract: sorted q9 SHA stayed `375fa52a42b6385d40091801807090bb18b6061ea6d5584bec0005bad4e5415e`.
- After max sorted delta vs NetworkX: `1.887379141862766e-14`.
- After max sorted delta vs closed form: `0.0`.
- Dtype preserved: `float64`.
- RNG: not used.

## Validation

- `OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 .venv/bin/python -m pytest tests/python/test_laplacian_spectrum_native.py tests/python/test_review_mode_regression_lock.py -k 'laplacian_spectrum' -q` -> `22 passed, 431 deselected`
- `.venv/bin/python -m py_compile python/franken_networkx/__init__.py tests/python/test_laplacian_spectrum_native.py tests/artifacts/perf/20260617T-laplacian-star-closed-form-coppercliff/laplacian_star_measure.py` -> passed
- `cargo fmt --check` -> passed
- `cargo check -p fnx-python --all-targets` -> passed
- `cargo clippy -p fnx-python --all-targets -- -D warnings` -> passed
- `git diff --check` -> passed
- `timeout 180s ubs python/franken_networkx/__init__.py tests/python/test_laplacian_spectrum_native.py` -> timed out after starting scan; no findings emitted.

## Score

Impact `5` x Confidence `5` / Effort `1` = `25.0`; keep.
