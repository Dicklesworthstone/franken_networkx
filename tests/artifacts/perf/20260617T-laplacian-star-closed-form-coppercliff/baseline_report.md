# br-r37-c1-04z53.9133 Baseline/Profile/Golden

Target expression:

```python
fnx.laplacian_spectrum(fnx.star_graph(798))
```

Environment:

- HEAD: `d39edc252189b9539ae4d7ef20dd5d358afc3eaa`
- Python: `3.13.7`
- NetworkX: `3.6.1`
- NumPy: `2.4.6`
- Thread env: `OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1`

## Direct Timing

Direct in-process timing includes graph construction and spectrum computation.

| implementation | samples | warmups | median seconds | mean seconds | p95 seconds |
|---|---:|---:|---:|---:|---:|
| FNX | 15 | 3 | 0.212556050974 | 0.215594915262 | 0.230115415994 |
| NetworkX | 15 | 3 | 0.031995131983 | 0.031998935256 | 0.033884814999 |

FNX median / NetworkX median: `6.643387221659`.

## Hyperfine Baseline

Hyperfine commands run five target calls per process to amortize interpreter startup.

| command | runs | mean seconds | stddev seconds | median seconds | range seconds |
|---|---:|---:|---:|---:|---|
| `fnx_5_calls` | 10 | 1.429784041600 | 0.020348181990 | 1.424398095700 | 1.403066145700 .. 1.456826211700 |
| `networkx_5_calls` | 10 | 0.537144778600 | 0.020067975275 | 0.537889503700 | 0.505996436700 .. 0.576206237700 |

Hyperfine summary: `networkx_5_calls` ran `2.66 +/- 0.11` times faster than `fnx_5_calls`.

## cProfile Hotspot

Profile captured five FNX target calls.

- Total profile time: `1.112892895995` seconds (`0.222578579199` seconds/call).
- Top frame: `{built-in method franken_networkx._fnx.symmetric_eigvals_rust}` at `1.076` seconds over five calls.
- Matrix densification is much smaller: `numpy.ascontiguousarray` `0.014` seconds, `csr_todense` `0.009` seconds.
- `star_graph` construction is negligible in this target: `0.004` seconds over five calls.

## Golden Contract

`fnx.star_graph(798)` has 799 nodes and 798 edges. For the unweighted simple star `K(1, 798)`, sorted Laplacian eigenvalues are:

- `0.0` once
- `1.0` repeated 797 times
- `799.0` once

Observed parity:

- FNX dtype: `float64`
- NetworkX dtype: `float64`
- Shape: `[799]`
- Max sorted delta FNX vs NetworkX: `7.327994793612726e-15`
- Max sorted delta FNX vs closed form: `1.4654943925052066e-14`
- `np.allclose(..., rtol=1e-8, atol=1e-8)`: true for FNX vs NetworkX and FNX vs closed form.
- q9 sorted contract SHA-256: `375fa52a42b6385d40091801807090bb18b6061ea6d5584bec0005bad4e5415e`

## Next-Pass Notes

A one-lever star closed-form should return a sorted `np.float64` array `[0.0, 1.0 x 797, 799.0]` before dense Laplacian construction and eigensolve only for exact unweighted simple `Graph` stars. Weighted edges under default `weight="weight"`, non-star graphs, directed graphs, multigraphs, subclasses, empty/error behavior, and non-string/callable weight cases should keep the current fallback route.

No blocker found for the one-lever implementation. Existing normalized/star and complete-Laplacian closed forms provide local precedent for a Python-wrapper guard.
