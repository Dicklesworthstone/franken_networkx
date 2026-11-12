# br-r37-c1-04z53.9132 - adjacency_spectrum complete_bipartite certificate detector

## Target

Prebuilt `G = fnx.complete_bipartite_graph(199, 200)` followed by
`fnx.adjacency_spectrum(G)`.

## Baseline

- Direct median: `0.025214917957782745s`
- Direct mean: `0.02872985356121457s`
- rch hyperfine mean: `0.7615846621200001s`
- rch hyperfine median: `0.76074530632s`
- cProfile: `1000` calls in `38.182s`
- Hotspot: Python complete-bipartite detector materialized edges, with
  `_materialize` at `16.107s`, detector cumulative `38.147s`, and
  `dict.get` at `6.191s`.
- Golden q9 complex SHA: `a63efbeb4292b532b153a35c7e56b3d04a922655ec7fb96fcf347a5518166929`
- Max sorted delta vs NetworkX: `3.126388037344441e-13`

## Lever

Route `_complete_bipartite_adjacency_spectrum_sorted_value_safe` through the
existing mutation-guarded complete-bipartite shape certificate first, then the
native unweighted detector, before falling back to the Python graph walk.

## After

- Direct median: `0.000022612977772951126s`
- Direct mean: `0.00003081543504127434s`
- rch hyperfine mean: `0.2586671296s`
- rch hyperfine median: `0.26156332260000004s`
- cProfile: `1000` calls in `0.013s`
- Certificate/native parts: `[199, 200]`
- Golden q9 complex SHA: `a63efbeb4292b532b153a35c7e56b3d04a922655ec7fb96fcf347a5518166929`
- Max sorted delta vs NetworkX: `3.126388037344441e-13`

## Speedup

- Direct median: `1115.06x`
- Direct mean: `932.32x`
- rch hyperfine mean: `2.94x`
- rch hyperfine median: `2.91x`
- Profile total: `2937.08x`

## Isomorphism Proof

- Ordering preserved: yes. The public route still returns sorted complex
  values for the complete-bipartite closed form.
- Tie-breaking unchanged: yes. The repeated nullspace eigenvalues remain equal
  complex zeros, so observable sorted-value ties are unchanged.
- Floating-point: deterministic formula unchanged from the previous
  complete-bipartite closed-form route; q9 complex SHA is identical before and
  after this detector-routing lever.
- RNG: N/A.
- Weighted graphs: still fall back when the requested edge attribute is present.
- Structural mutations: certificate path is gated by node and edge mutation
  sequences; the new regression test rewires an edge without changing edge
  count and proves fallback parity with NetworkX.

## Validation

- `rch exec -- .venv/bin/python -m pytest tests/python/test_adjacency_spectrum_native.py tests/python/test_laplacian_spectrum_native.py -q` -> `32 passed`
- `.venv/bin/python -m py_compile python/franken_networkx/__init__.py tests/python/test_adjacency_spectrum_native.py tests/python/test_laplacian_spectrum_native.py`
- `cargo fmt --check`
- `git diff --check`
- `rch exec -- cargo check -p fnx-python --all-targets`
- `timeout 60s ubs python/franken_networkx/__init__.py tests/python/test_adjacency_spectrum_native.py` timed out with no findings output before the bound.

## Score

Impact `5` x Confidence `5` / Effort `1` = `25.0`; keep.
