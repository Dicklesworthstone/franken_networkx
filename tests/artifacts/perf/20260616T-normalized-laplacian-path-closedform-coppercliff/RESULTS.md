# br-r37-c1-apzym normalized_laplacian_spectrum path graph

## Target

- Case: `fnx.normalized_laplacian_spectrum(fnx.path_graph(399))`
- Profile-backed hotspot: dense normalized Laplacian matrix materialization followed by dense `eigvalsh`
- Lever: exact unweighted path `Graph` closed-form spectrum `1 - cos(pi * k / (n - 1))`

## Baseline

- Direct median: `0.3784449329832569s`
- Direct mean: `0.3486318081966601s`
- rch hyperfine mean: `0.8197652523400001s`
- rch hyperfine median: `0.55531914294s`
- Profile: 3 calls spent `3.813s` in dense `np.linalg.eigvalsh`
- Golden sorted q9 SHA256: `8ae34d32768716c854756de74769672c391325d802e47e46a50ad5659dd4b47f`
- Max sorted delta vs NetworkX: `0.0`

## After

- Direct median: `0.0009090020321309566s`
- Direct mean: `0.0011471826233901083s`
- rch hyperfine mean: `0.29514613134s`
- rch hyperfine median: `0.27560222114s`
- Profile: `1000` calls in `1.537s`; dense matrix construction and eigensolver are absent
- Golden sorted q9 SHA256: `8ae34d32768716c854756de74769672c391325d802e47e46a50ad5659dd4b47f`
- Max sorted delta vs NetworkX: `1.7763568394002505e-15`

## Result

- Direct median speedup: `416.33x`
- Direct mean speedup: `303.90x`
- rch mean speedup: `2.78x`
- rch median speedup: `2.01x`
- Score: Impact `5` x Confidence `5` / Effort `1` = `25.0`

## Isomorphism Proof

- Ordering: formula is monotone for `k = 0..n-1`, so output is already sorted ascending
- Floating point: returns `float64` and sets the first value to `-0.0` to preserve the raw q9 SHA produced by the dense route
- Tie-breaking: no ambiguous ordering beyond the fixed endpoint values
- RNG: no random state read or mutated
- Fallbacks: non-`Graph`, invalid-weight, weighted-edge, non-path, disconnected, 0-node, and non-simple path cases keep existing routes
- Golden SHA: raw and zero-normalized q9 SHA256 match NetworkX exactly

## Validation

- `rch exec -- .venv/bin/python -m pytest tests/python/test_laplacian_spectrum_native.py tests/python/test_adjacency_spectrum_native.py -q` -> `26 passed`
- `.venv/bin/python -m py_compile python/franken_networkx/__init__.py tests/python/test_laplacian_spectrum_native.py tests/python/test_adjacency_spectrum_native.py`
- `cargo fmt --check`
- `git diff --check`
- `timeout 60s ubs python/franken_networkx/__init__.py tests/python/test_laplacian_spectrum_native.py` -> timed out without findings output
