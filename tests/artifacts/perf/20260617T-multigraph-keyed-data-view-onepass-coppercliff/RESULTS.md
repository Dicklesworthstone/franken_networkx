# br-r37-c1-3c9h7 MultiGraph Keyed Data Edge View

Target: `MultiGraph.edges(keys=True, data=True)` on freshly constructed
attributed exact-int multigraphs.

Candidate: mirror the successful MultiDiGraph one-pass keyed data edge-view
primitive for MultiGraph, then refine the fallback to avoid a per-edge temporary
element vector for the `keys=True, data=True` tuple shape.

Verdict: rejected. Hyperfine and the construction-only survey moved in the
right direction, but the comparable cProfile gate regressed and the targeted
`_native_edge_view_list` cost stayed flat, so Score < 2.0 and no source change
was kept.

## Baseline

- Survey `multigraph_attr` digest match: `true`
- FNX median: `0.01924060395685956s`
- NetworkX median: `0.015621497994288802s`
- FNX/NX ratio: `1.2316747064778228`
- Digest: `50644c550f48ebc209b8fa5bb649acf1961385c2b71d65f0a572cb3e2a22ae99`
- Hyperfine loop50 FNX mean: `2.95305603176s`
- Hyperfine loop50 NetworkX mean: `2.50489268436s`
- Profile total: `9.663s / 160` builds
- `__init__.py:2061(__call__)`: `1.617s / 160`
- `_native_edge_view_list`: `1.541s / 160`
- `_try_add_attr_edges_from_batch`: `2.725s / 160`

## Candidate

- Survey `multigraph_attr` digest match: `true`
- FNX median: `0.018244036997202784s`
- NetworkX median: `0.014994992990978062s`
- FNX/NX ratio: `1.2166752600804516`
- Digest: `50644c550f48ebc209b8fa5bb649acf1961385c2b71d65f0a572cb3e2a22ae99`
- Hyperfine loop50 FNX mean: `2.70592757864s`
- Hyperfine loop50 NetworkX mean: `2.30309902344s`
- Profile total: `10.016s / 160` builds
- `__init__.py:2061(__call__)`: `1.628s / 160`
- `_native_edge_view_list`: `1.543s / 160`
- `_try_add_attr_edges_from_batch`: `2.863s / 160`

## Notes

The MultiGraph edge-view profile is dominated by the existing native list path,
but this tuple-shape specialization did not reduce that native cost. The next
attempt should use a different primitive: avoid the undirected seen-set/string
canonicalization work or replace the MultiGraph keyed edge layout directly,
rather than specializing tuple assembly.
