# br-r37-c1-7wbqo adjacency_spectrum path_graph closed form

## Target

`fnx.adjacency_spectrum(fnx.path_graph(799))`

## Baseline

- Direct FNX median: `0.24118351400829852 s/call`.
- Direct FNX mean: `0.24562686980934814 s/call`.
- rch hyperfine mean for three calls: `1.04478315332 s`.
- rch hyperfine median for three calls: `1.03745141932 s`.
- Profile over 3 calls: `0.690 s / 0.713 s` in `_fnx.symmetric_eigvals_rust`.
- Canonical q8 sorted SHA: `0870082253a49163621f75e24a3791e03373431c815f1b455e87c8f2e9b64a88`.

## After

- Direct FNX median: `0.0032005839748308063 s/call`.
- Direct FNX mean: `0.0034256585912468534 s/call`.
- rch hyperfine mean for three calls: `0.26644809484500004 s`.
- rch hyperfine median for three calls: `0.26536453572000007 s`.
- Profile over 100 calls: dense adjacency construction and eigensolver are
  absent; `_path_adjacency_spectrum_sorted_value_safe` costs `0.311 s` total.

## Proof

- FNX canonical q8 sorted SHA: `0870082253a49163621f75e24a3791e03373431c815f1b455e87c8f2e9b64a88`.
- NetworkX canonical q8 sorted SHA: `0870082253a49163621f75e24a3791e03373431c815f1b455e87c8f2e9b64a88`.
- Max sorted absolute delta vs NetworkX: `2.5979218776228663e-14`.
- Dtype parity: FNX and NetworkX both return `complex128`.
- Ordering/tie behavior: no raw-order contract is changed; this API is locked to
  dtype plus sorted-value parity in the current tests.
- Floating point surface: analytic `2*cos(k*pi/(n+1))` values are converted to
  `complex128`.
- RNG surface: unchanged; no RNG is used.
- Fallback surface: the guard only accepts exact simple unweighted path Graphs.
  Weighted paths, directed graphs, non-path graphs, disconnected degree-lookalikes,
  and empty/error behavior use the existing route.

## Validation

```bash
rch exec -- .venv/bin/python -m pytest tests/python/test_adjacency_spectrum_native.py -q
rch exec -- .venv/bin/python -m py_compile python/franken_networkx/__init__.py tests/python/test_adjacency_spectrum_native.py
cargo fmt --check
git diff --check
```

`ubs python/franken_networkx/__init__.py tests/python/test_adjacency_spectrum_native.py`
hung in the Python scanner and was interrupted.

## Score

Impact `75.36` (direct median speedup) x Confidence `0.95` / Effort `1` =
`71.59`. The rch hyperfine command improved end to end from `1.04478315332 s`
to `0.26644809484500004 s`.
