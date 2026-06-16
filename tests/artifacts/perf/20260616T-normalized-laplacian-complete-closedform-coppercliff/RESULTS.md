# br-r37-c1-bwizc normalized_laplacian_spectrum complete graph

## Target

- Case: `fnx.normalized_laplacian_spectrum(fnx.complete_graph(399))`
- Profile-backed hotspot: dense normalized Laplacian matrix construction followed by dense `eigvalsh`
- Lever: exact unweighted simple complete `Graph` closed-form spectrum `[0, n / (n - 1) repeated n - 1]`

## Baseline

- Direct median: `0.07446279999567196s`
- Direct mean: `0.12365103919291869s`
- rch hyperfine mean for 3 calls: `0.5138697156400001s`
- Profile: 3 calls spent `5.500s` in dense `eigvalsh` and `0.232s` building `normalized_laplacian_matrix`
- Golden sorted q9 SHA256: `1b6d151ae1e0aaa7d8cfa14f0ab12b5d04c8e38ae1b02d1c5c0378c351013d59`
- Max sorted delta vs NetworkX: `1.1102230246251565e-15`

## After

- Direct median: `0.00035284896148368716s`
- Direct mean: `0.0003096967935562134s`
- rch hyperfine mean for 3 calls: `0.26389789252000007s`
- Profile: 1000 calls spent `0.123s`; dense `eigvalsh` and matrix construction are absent
- Golden sorted q9 SHA256: `1b6d151ae1e0aaa7d8cfa14f0ab12b5d04c8e38ae1b02d1c5c0378c351013d59`
- Max sorted delta vs NetworkX: `5.551115123125783e-15`

## Result

- Direct median speedup: `211.03x`
- Direct mean speedup: `399.26x`
- rch three-call mean speedup: `1.95x`
- Score: Impact `5` x Confidence `5` / Effort `1` = `25.0`

## Isomorphism Proof

- Ordering: returned vector is already sorted ascending, matching `np.sort(np.linalg.eigvalsh(...))`
- Floating point: uses deterministic `float(n) / float(n - 1)` and preserves `float64`
- Tie-breaking: no tie-dependent branch; multiplicity is fixed by the complete graph spectrum
- RNG: no random state read or mutated
- Fallbacks: non-`Graph`, empty graph, incomplete graph, and weighted-edge cases keep the existing matrix/eigensolver route
- Golden SHA: raw and zero-normalized q9 SHA256 match NetworkX exactly

## Validation

- `rch exec -- .venv/bin/python -m pytest tests/python/test_laplacian_spectrum_native.py tests/python/test_adjacency_spectrum_native.py -q` -> `19 passed`
- `.venv/bin/python -m py_compile python/franken_networkx/__init__.py tests/python/test_laplacian_spectrum_native.py tests/python/test_adjacency_spectrum_native.py`
- `cargo fmt --check`
- `git diff --check`
- `timeout 60s ubs python/franken_networkx/__init__.py tests/python/test_laplacian_spectrum_native.py` -> timed out without findings output
