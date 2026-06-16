# br-r37-c1-04z53.9130 normalized_laplacian_spectrum complete bipartite detector

## Target

- `G = fnx.complete_bipartite_graph(199, 200); fnx.normalized_laplacian_spectrum(G)`
- Profile-backed hotspot after `681afb202`: the dense eigensolver was gone, but 1000 calls still spent `38.604s` total, with `16.209s` in Python `EdgeDataView._materialize`, `11.771s` in `_complete_bipartite_normalized_laplacian_spectrum_sorted_value_safe`, `6.265s` in `dict.get`, and `3.810s` in `_gen`.

## Lever

- Add a native `PyGraph._native_complete_bipartite_unweighted_parts(weight)` predicate.
- Route the normalized-Laplacian complete-bipartite guard through that native predicate before allocating the `[0, 1 repeated n - 2, 2]` `float64` spectrum.
- The native predicate checks connected bipartiteness, side sizes, edge count, degree contract, and both Rust/Python edge-attribute stores for weighted fallback.

## Evidence

- Baseline direct prebuilt-graph proof: median `0.022027571976650506s`, mean `0.02803058938588947s`.
- After direct prebuilt-graph proof: median `0.0002623070031404495s`, mean `0.000293135573156178s`.
- Direct speedup: `83.98x` median, `95.62x` mean.
- Baseline rch hyperfine repeated-call payload: mean `0.72117194222s`, median `0.7223162914200001s`.
- After rch hyperfine repeated-call payload: mean `0.27480533034000004s`, median `0.27246826914000005s`.
- Rch payload mean speedup: `2.62x`.
- Baseline profile: `38.604s / 1000` calls.
- After profile: `0.185s / 1000` calls; Python edge materialization frames are absent, and the native predicate accounts for `0.162s`.
- Golden formula q9 SHA stayed `f8730fc3385a456fc1da163fc04072028ae8798e67b4be387e7e2afe3036152f`.
- Maximum sorted-value delta versus NetworkX after the lever: `5.551115123125783e-15`.

## Validation

- `rch exec -- cargo check -p fnx-python --all-targets`.
- `rch exec -- maturin develop --release --features pyo3/abi3-py310`.
- `rch exec -- .venv/bin/python -m pytest tests/python/test_laplacian_spectrum_native.py tests/python/test_adjacency_spectrum_native.py -q`: `31 passed`.
- `.venv/bin/python -m py_compile python/franken_networkx/__init__.py tests/python/test_laplacian_spectrum_native.py tests/python/test_adjacency_spectrum_native.py`.
- `cargo fmt --check`.
- `git diff --check`.
- `rch exec -- cargo clippy -p fnx-python --all-targets -- -D warnings`.
- `timeout 60s ubs crates/fnx-python/src/lib.rs python/franken_networkx/__init__.py tests/python/test_laplacian_spectrum_native.py`: Rust scan finished; command timed out in Python scan with no findings output.

## Score

- Impact `5` x Confidence `5` / Effort `2` = `12.5`; keep.

## Residual

- The complete-bipartite detector gap is closed for this spectral route. Remaining repeated-call time is dominated by the native O(E) predicate and fixed import/wrapper overhead; further complete-bipartite work should use a mutation-guarded graph-shape certificate rather than another detector scan.
