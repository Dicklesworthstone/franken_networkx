# br-r37-c1-2rrjs adjacency_spectrum complete_graph closed form

## Target

`fnx.adjacency_spectrum(fnx.complete_graph(399))`

## Baseline

- Direct FNX median: `0.057802908995654434 s/call`.
- Direct FNX mean: `0.06275330459466204 s/call`.
- rch hyperfine mean for three calls: `0.5211758714000001 s`.
- rch hyperfine median for three calls: `0.5173038181 s`.
- Profile over 3 calls: `0.081 s` in `_fnx.symmetric_eigvals_rust` and
  `0.051 s` in `adjacency_matrix` / `to_scipy_sparse_array`.
- Canonical q9 sorted SHA: `545e3c179d9a385caf9515ddb614bf16596323fb74ef87f6cb9d03ef99a682af`.

## After

- Direct FNX median: `0.0045693070278503 s/call`.
- Direct FNX mean: `0.004830716197223713 s/call`.
- rch hyperfine mean for three calls: `0.27548272936 s`.
- rch hyperfine median for three calls: `0.26885294226 s`.
- Profile over 100 calls: dense matrix construction and eigensolver are absent;
  `_native_is_complete_unweighted_graph` costs `0.018 s` total.

## Proof

- FNX canonical q9 sorted SHA: `545e3c179d9a385caf9515ddb614bf16596323fb74ef87f6cb9d03ef99a682af`.
- NetworkX canonical q9 sorted SHA: `545e3c179d9a385caf9515ddb614bf16596323fb74ef87f6cb9d03ef99a682af`.
- Max sorted absolute delta vs NetworkX: `7.958078640513122e-13`.
- Dtype parity: FNX and NetworkX both return `complex128`.
- Ordering/tie behavior: no raw-order contract is changed; this API is locked to
  dtype plus sorted-value parity in the current tests.
- Floating point surface: analytic integer eigenvalues are converted to
  `complex128`; no iterative numerical solver is used on the guarded path.
- RNG surface: unchanged; no RNG is used.
- Fallback surface: the guard only accepts exact simple `Graph` instances that
  are structurally complete and have no requested weight key in native or
  Python edge-attr storage. Weighted complete graphs, directed graphs,
  non-complete graphs, and empty/error behavior use the existing route.

## Validation

```bash
rch exec -- cargo check -p fnx-python --lib --features pyo3/abi3-py310
rch exec -- maturin develop --profile release-perf --features pyo3/abi3-py310
rch exec -- .venv/bin/python -m pytest tests/python/test_adjacency_spectrum_native.py -q
cargo fmt --package fnx-python --check
rch exec -- .venv/bin/python -m py_compile python/franken_networkx/__init__.py tests/python/test_adjacency_spectrum_native.py
git diff --check
rch exec -- cargo clippy -p fnx-python --lib --features pyo3/abi3-py310 -- -D warnings
```

`ubs crates/fnx-python/src/lib.rs python/franken_networkx/__init__.py tests/python/test_adjacency_spectrum_native.py`
finished the Rust scan without findings output, then hung in the Python scanner
and was interrupted.

## Score

Impact `12.65` (direct median speedup) x Confidence `0.95` / Effort `2` =
`6.01`. The rch hyperfine command also improved end to end from
`0.5211758714000001 s` to `0.27548272936 s`.
