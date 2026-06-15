# br-r37-c1-04z53.9110 Pass 1 Evidence

Scope: evidence-only baseline/profile/golden for
`list(DG.reverse(copy=False).edges())`.

No source files were edited. The workload graph is
`DiGraph(watts_strogatz_graph(1200, 8, 0.2, seed=3))`, imported from the live
checkout at `/data/projects/franken_networkx/python/franken_networkx/__init__.py`.

## Baseline

Command:

```bash
rch exec -- hyperfine --warmup 3 --runs 10 --export-json tests/artifacts/perf/20260615T-reverse-view-edges-coppercliff/hyperfine_reverse_edges_baseline.json --command-name fnx 'PYTHONPATH=/data/projects/franken_networkx/python:/data/projects/franken_networkx .venv/bin/python tests/artifacts/perf/20260615T-reverse-view-edges-coppercliff/reverse_view_edges_harness.py bench-fnx --loops 300' --command-name nx 'PYTHONPATH=/data/projects/franken_networkx/python:/data/projects/franken_networkx .venv/bin/python tests/artifacts/perf/20260615T-reverse-view-edges-coppercliff/reverse_view_edges_harness.py bench-nx --loops 300'
```

Result:

- FNX mean: 1.7377445066s for 300 loops, 5.7924816887ms per loop.
- NetworkX mean: 0.5276182837s for 300 loops, 1.7587276123ms per loop.
- Ratio: NetworkX 3.29x faster by mean, 3.26x faster by median.

## Profile

Command:

```bash
rch exec -- env PYTHONPATH=/data/projects/franken_networkx/python:/data/projects/franken_networkx .venv/bin/python tests/artifacts/perf/20260615T-reverse-view-edges-coppercliff/reverse_view_edges_harness.py profile-fnx --loops 300 --output tests/artifacts/perf/20260615T-reverse-view-edges-coppercliff/profile_fnx_reverse_edges.txt
```

Top cumulative frames:

- `reverse_view_edges_harness.py:82(target)`: 5.160s / 300 calls.
- `python/franken_networkx/__init__.py:35261(_ReverseEdgeView.__call__)`: 5.127s / 300 calls.
- `python/franken_networkx/__init__.py:34637(_ReverseDirectedViewBase._edges)`: 5.126s / 300 calls, 1.420s self.
- `python/franken_networkx/__init__.py:1138(<genexpr>)`: 1.929s.
- `python/franken_networkx/__init__.py:1252(__getitem__)`: 1.375s.
- `python/franken_networkx/__init__.py:36600(_private_pred_mapping)`: 0.512s.

Single hottest implementation surface:
`_ReverseDirectedViewBase._edges`, specifically the no-data reverse edge path
walking `self._graph.pred[source].items()` through Python predecessor-row
mapping/AtlasView layers and appending tuples.

## Golden

Command:

```bash
PYTHONPATH=/data/projects/franken_networkx/python:/data/projects/franken_networkx .venv/bin/python tests/artifacts/perf/20260615T-reverse-view-edges-coppercliff/reverse_view_edges_harness.py golden
```

Aggregate SHA:

```text
FNX 2e13b616a395c926d715ab7843bd713b1626a5cba9957d1348916f059c5105f3
NX  2e13b616a395c926d715ab7843bd713b1626a5cba9957d1348916f059c5105f3
```

Parity cases all matched:

- Edge order.
- `edges(data=True)`.
- `edges(data="w", default=-999)`.
- Live reverse view after source mutation.
- Frozen mutation error surface for `add_edge`, `remove_node`, and `clear`.

## Opportunity

Score >= 2.0 appears plausible. The baseline gap is 3.29x by mean and the
profile has one dominant surface. The next lever candidate is a specialized
reverse-view no-data edge materializer for concrete `DiGraph` that bypasses
Python `pred[source].items()`/AtlasView layers while preserving node-major
reverse edge order, live view semantics, frozen mutation errors, and data/key
variants by leaving those variants on the existing path unless separately
proved.
