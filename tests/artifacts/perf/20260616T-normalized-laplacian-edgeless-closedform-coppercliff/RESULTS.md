# br-r37-c1-ry1zl normalized_laplacian_spectrum edgeless graph

## Target

- Case: `fnx.normalized_laplacian_spectrum(fnx.empty_graph(799))`
- Profile-backed hotspot: dense normalized Laplacian matrix materialization followed by dense `eigvalsh`
- Lever: exact edgeless `Graph` closed-form spectrum, sorted `float64` zeros

## Baseline

- Direct median: `0.7799348229891621s`
- Direct mean: `0.7393987543376473s`
- rch hyperfine mean: `2.40375488468s`
- rch hyperfine median: `1.72823388368s`
- Profile: one call spent `5.462s` in dense `np.linalg.eigvalsh`
- Golden sorted q9 SHA256: `243ec6ae37a430bfc5880a78f3bca1a7f8a85d05602286df3094554a6cb323e7`
- Max sorted delta vs NetworkX: `0.0`

## After

- Direct median: `0.000004859000910073519s`
- Direct mean: `0.00001379221212118864s`
- rch hyperfine mean: `0.2489021926s`
- rch hyperfine median: `0.2441005836s`
- Profile: `10000` calls in `0.048s`; dense matrix construction and eigensolver are absent
- Golden sorted q9 SHA256: `243ec6ae37a430bfc5880a78f3bca1a7f8a85d05602286df3094554a6cb323e7`
- Max sorted delta vs NetworkX: `0.0`

## Result

- Direct median speedup: `160513.41x`
- Direct mean speedup: `53609.87x`
- rch mean speedup: `9.66x`
- rch median speedup: `7.08x`
- Score: Impact `5` x Confidence `5` / Effort `1` = `25.0`

## Isomorphism Proof

- Ordering: returned vector is already sorted ascending, matching sorted zero eigenvalues
- Floating point: returns `np.zeros(n, dtype=np.float64)`, matching NetworkX dtype
- Tie-breaking: all eigenvalues are equal zeros, so no tie-dependent branch is introduced
- RNG: no random state read or mutated
- Fallbacks: non-`Graph`, non-string/non-`None` weights, non-edgeless graphs, and 0-node graphs keep the existing route
- Golden SHA: raw q9 SHA256 matches NetworkX exactly

## Validation

- `rch exec -- .venv/bin/python -m pytest tests/python/test_laplacian_spectrum_native.py tests/python/test_adjacency_spectrum_native.py -q` -> `24 passed`
- `.venv/bin/python -m py_compile python/franken_networkx/__init__.py tests/python/test_laplacian_spectrum_native.py tests/python/test_adjacency_spectrum_native.py`
- `cargo fmt --check`
- `git diff --check`
- `timeout 60s ubs python/franken_networkx/__init__.py tests/python/test_laplacian_spectrum_native.py` -> timed out without findings output
