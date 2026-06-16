# br-r37-c1-04z53.9131 normalized_laplacian_spectrum complete bipartite certificate

## Target

- `G = fnx.complete_bipartite_graph(199, 200); fnx.normalized_laplacian_spectrum(G)`
- Profile-backed hotspot after `540012aba`: the detector was native but still scanned the graph. Baseline profile spent `0.161s / 1000` calls in `_native_complete_bipartite_unweighted_parts`, with `0.182s / 1000` calls total.

## Lever

- Stamp a private complete-bipartite shape certificate from `complete_bipartite_graph`.
- Accept the certificate only when `nodes_seq` and `edges_seq` still match, side sizes match `node_count`/`edge_count`, and dirty edge attrs cannot affect the selected weight mode.
- Fall back to the native detector for mutated, dirty weighted, incomplete, disconnected, or non-complete-bipartite graphs.

## Evidence

- Baseline direct prebuilt-graph proof: median `0.0002581290318630636s`, mean `0.0002809722791425884s`.
- After direct prebuilt-graph proof: median `0.000012103002518415451s`, mean `0.00001877414927418743s`.
- Direct speedup: `21.33x` median, `14.97x` mean.
- Baseline rch hyperfine 1000-call payload: mean `0.44488952082s`, median `0.44112767282000004s`.
- After rch hyperfine 1000-call payload: mean `0.2663994009s`, median `0.2741636689s`.
- Rch payload mean speedup: `1.67x`.
- Baseline profile: `0.182s / 1000` calls.
- After profile: `0.020s / 1000` calls; `_native_complete_bipartite_unweighted_parts` is absent from the hot path.
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

- Impact `4` x Confidence `5` / Effort `2` = `10.0`; keep.

## Residual

- The complete-bipartite normalized-Laplacian route is now down to fixed Python wrapper/import/array-allocation overhead for this graph family. Re-profile other spectral families or construction paths instead of further scanning work here.
