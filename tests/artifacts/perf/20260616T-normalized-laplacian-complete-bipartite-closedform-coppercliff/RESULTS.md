# br-r37-c1-laezf normalized_laplacian_spectrum complete bipartite

## Target

- `fnx.normalized_laplacian_spectrum(fnx.complete_bipartite_graph(199, 200))`
- Profile-backed hotspot: baseline cProfile spent `8.971s / 3` calls in dense `np.linalg.eigvalsh` and `0.194s / 3` calls in `normalized_laplacian_matrix`.

## Lever

- Add a guarded unweighted simple `Graph` complete-bipartite closed-form route before matrix construction and dense eigensolve.
- Spectrum formula: `[0, 1 repeated n - 2, 2]`, emitted as sorted `float64`.
- Weighted graphs, disconnected graphs, non-bipartite graphs, and incomplete bipartite graphs stay on the existing matrix/eigensolver path.

## Evidence

- Baseline direct proof: median `1.9187178509891964s`, mean `2.1882990165962837s`.
- After direct proof: median `0.025215058005414903s`, mean `0.03243402079679072s`.
- Direct speedup: `76.09x` median, `67.47x` mean.
- Baseline rch hyperfine: mean `2.1965276944000003s`, median `3.086689159s`.
- After rch hyperfine: mean `0.37238843866000004s`, median `0.35391925786000006s`.
- Rch mean speedup: `5.90x`.
- Golden q9 SHA stayed `f8730fc3385a456fc1da163fc04072028ae8798e67b4be387e7e2afe3036152f`.
- Maximum sorted-value delta versus NetworkX after the lever: `5.551115123125783e-15`.
- After profile: 1000 calls no longer enter dense `np.linalg.eigvalsh`; remaining cost is complete-bipartite shape detection (`39.028s / 1000` calls total).

## Validation

- `rch exec -- .venv/bin/python -m pytest tests/python/test_laplacian_spectrum_native.py tests/python/test_adjacency_spectrum_native.py -q`: `30 passed`.
- `.venv/bin/python -m py_compile python/franken_networkx/__init__.py tests/python/test_laplacian_spectrum_native.py tests/python/test_adjacency_spectrum_native.py`.
- `cargo fmt --check`.
- `git diff --check`.
- `timeout 60s ubs python/franken_networkx/__init__.py tests/python/test_laplacian_spectrum_native.py`: timed out with no findings output.

## Score

- Impact `5` x Confidence `5` / Effort `1` = `25.0`; keep.

## Residual

- The dense normalized-Laplacian eigensolve gap is closed for complete bipartite graphs. The next deeper target is the profiled Python-side shape detector/materialization cost or another spectral family that still reaches dense eigensolve.
