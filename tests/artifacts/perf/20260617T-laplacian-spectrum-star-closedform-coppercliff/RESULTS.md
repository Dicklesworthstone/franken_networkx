# br-r37-c1-04z53.9133 laplacian_spectrum star_graph closed form

## Target

- Workload: `fnx.laplacian_spectrum(fnx.star_graph(798))`.
- Baseline profile: current HEAD spent `0.239s` of one call in `_fnx.symmetric_eigvals_rust` after Laplacian matrix construction.
- Alien primitive: graph symmetry / equitable partition for star graphs. The Laplacian spectrum of a star on `n` nodes is `[0, 1 repeated n-2, n]`.

## Change

Exact unweighted simple `Graph` stars now return the sorted `float64` closed form before dense matrix construction and eigensolver routing.

Guard conditions:
- exact `Graph` only
- `weight is None` or `weight` is a string
- `n >= 2`
- edge count is `n - 1`
- `n == 2`: both degrees are `1`
- `n > 2`: one center has degree `n - 1`, all other nodes have degree `1`
- if a string weight attribute appears on any edge, fallback is used

## Behavior Proof

- Ordering preserved: yes. Public `laplacian_spectrum` returns eigenvalues sorted ascending; the closed form is emitted in ascending order.
- Tie-breaking unchanged: yes. Eigenvalues are scalar values only; repeated `1.0` eigenvalues carry no eigenvector pairing.
- Floating-point: deterministic `float64` values `[0.0, 1.0..., float(n)]`; sorted-value parity with NetworkX preserved with q9 near-zero-normalized SHA `267e2d0347ebe4856bb092e75e3bada1a43ec05673dae00d2af9a4852fe9da43`.
- RNG: N/A.
- Golden checks: `sha256sum -c artifact_sha256.txt` passed.
- Weighted fallback: `fnx._star_laplacian_spectrum_sorted_value_safe(G, "weight") is None` when a star edge carries `weight`, and public output stays sorted-value equal to NetworkX.
- Non-star fallback: `path_graph(31)` is rejected by the helper and public output stays sorted-value equal to NetworkX.

## Benchmarks

Local hyperfine, `--warmup 3 --runs 10`, process includes import and graph construction:

| case | before mean | after mean | speedup |
| --- | ---: | ---: | ---: |
| FNX one call | `0.58115660612s` | `0.31944316520s` | `1.82x` |
| NetworkX comparator | `2.50697061402s` | `3.91703541540s` | comparator moved |

Direct prebuilt FNX timing:

| case | before median | after median | speedup |
| --- | ---: | ---: | ---: |
| `laplacian_spectrum(star_graph(798))` | `0.22721471701515839s` | `0.0006161179626360536s` | `368.78x` |

After profile:
- `1000` calls in `0.731s`.
- Dense matrix construction and eigensolver frames are absent.
- Remaining dominant cost is the guard's structural scan (`_star_laplacian_spectrum_sorted_value_safe`).

Score: Impact `5` x Confidence `5` / Effort `1` = `25.0`; keep.

## Validation

- `env PYTHONPATH=python .venv/bin/python -m pytest tests/python/test_laplacian_spectrum_native.py -q` -> `19 passed`
- `env PYTHONPATH=python .venv/bin/python -m py_compile python/franken_networkx/__init__.py tests/python/test_laplacian_spectrum_native.py` -> passed
- `git diff --check -- python/franken_networkx/__init__.py tests/python/test_laplacian_spectrum_native.py` -> passed
- `timeout 120s ubs python/franken_networkx/__init__.py tests/python/test_laplacian_spectrum_native.py` -> timed out after starting Python scan; no findings were emitted before timeout

## Residual

The star eigensolver gap is closed. The shifted residual for repeated star calls is the Python structural guard scan. Next route should be a mutation-guarded star shape certificate or a native detector, not another dense eigensolver bypass.
