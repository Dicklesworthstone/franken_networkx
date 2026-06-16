# br-r37-c1-9hiwv normalized_laplacian_spectrum cycle graph

## Target

- Case: `fnx.normalized_laplacian_spectrum(fnx.cycle_graph(399))`
- Profile-backed hotspot: dense normalized Laplacian matrix materialization followed by dense `eigvalsh`
- Lever: exact unweighted cycle `Graph` closed-form spectrum `sort(1 - cos(2*pi*k/n))`

## Baseline

- Direct median: `1.8982809410081245s`
- Direct mean: `2.1585972546134142s`
- rch hyperfine mean: `1.3861024239800002s`
- rch hyperfine median: `0.8533974257800001s`
- Profile: 3 calls spent `7.955s` in dense `np.linalg.eigvalsh`
- Golden sorted q9 SHA256: `5a3d5206eb581a6b24816e41ab1d23a54828daac5c4c49042bd4767c71a5d2cd`
- Max sorted delta vs NetworkX: `3.3306690738754696e-15`

## After

- Direct median: `0.0003566949744708836s`
- Direct mean: `0.00055074478732422s`
- rch hyperfine mean: `0.26212503294000006s`
- rch hyperfine median: `0.25593295294s`
- Profile: `1000` calls in `1.362s`; dense matrix construction and eigensolver are absent
- Golden sorted q9 SHA256: `5a3d5206eb581a6b24816e41ab1d23a54828daac5c4c49042bd4767c71a5d2cd`
- Max sorted delta vs NetworkX: `1.7763568394002505e-15`

## Result

- Direct median speedup: `5321.86x`
- Direct mean speedup: `3919.41x`
- rch mean speedup: `5.29x`
- rch median speedup: `3.33x`
- Score: Impact `5` x Confidence `5` / Effort `1` = `25.0`

## Isomorphism Proof

- Ordering: formula result is sorted before return, matching dense sorted eigenvalues
- Floating point: returns `float64` values from the deterministic cosine formula
- Tie-breaking: repeated cycle eigenvalues are sorted numerically, with no node-order dependence
- RNG: no random state read or mutated
- Fallbacks: non-`Graph`, invalid-weight, weighted-edge, non-cycle, disconnected two-regular, and too-small graph cases keep existing routes
- Golden SHA: raw q9 SHA256 matches NetworkX exactly

## Validation

- `rch exec -- .venv/bin/python -m pytest tests/python/test_laplacian_spectrum_native.py tests/python/test_adjacency_spectrum_native.py -q` -> `28 passed`
- `.venv/bin/python -m py_compile python/franken_networkx/__init__.py tests/python/test_laplacian_spectrum_native.py tests/python/test_adjacency_spectrum_native.py`
- `cargo fmt --check`
- `git diff --check`
- `timeout 60s ubs python/franken_networkx/__init__.py tests/python/test_laplacian_spectrum_native.py` -> timed out without findings output
