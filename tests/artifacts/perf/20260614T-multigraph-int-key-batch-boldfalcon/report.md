# MultiGraph Int-Key Batch Rejection

Bead: `br-r37-c1-04z53.85`

## Target

The current construction sweep showed `multigraph_int_keys` as the top remaining
construction residual after the string-key batch route:

- Fixture: fresh `MultiGraph.add_edges_from([(i, i + 1, i), ...])` with 50,000
  keyed edges.
- Baseline FNX direct median: `0.1725485969800502s`.
- Baseline FNX direct mean: `0.1761585411758543s`.
- Baseline NetworkX direct median: `0.12237702199490741s`.
- Baseline ratio: FNX was `1.409975452640371x` slower than NetworkX on this
  focused harness run.
- Baseline hyperfine mean: `1.44332349766s`.
- Baseline cProfile: `_multi_add_edges_from` consumed `1.125s` over 5 builds,
  including `250000` Python `add_edge` calls and `0.621s` in the native per-edge
  `MultiGraph.add_edge` method.

## One Lever Tried

Added a native fresh-graph `(int, int, int)` keyed edge batch route for exact int
endpoints and exact non-bool, nonnegative int keys that fit the native key slot.
Unsupported shapes fell back before mutation: duplicates, negative keys, bool
keys, int subclasses, tuple input, global attrs, data dicts, and non-fresh
graphs.

## Result

- Candidate FNX direct median: `0.16986864499631338s`.
- Candidate FNX direct mean: `0.1702792654554783s`.
- Direct median speedup: `1.0157766136522428x`.
- Direct mean speedup: `1.034527255591863x`.
- Candidate hyperfine mean: `1.46824522606s`.
- Hyperfine mean speedup: `0.9830261812143759x` (regression).
- Candidate cProfile dropped to `46` calls over 5 builds and removed the Python
  per-edge `add_edge` loop, but the native batch helper itself consumed `0.820s`
  and did not translate into a process-level win.

## Golden Proof

- Baseline and candidate bundle SHA:
  `001673863110955f5aa86e46fdb5d633dbc4836a87cee39dec83a20a6188eef2`.
- Direct construction digest:
  `3a178de5d183ef7f5908b169571990e3b38be9c6632e2d31392796389ce82d1e`.
- Golden cases matched NetworkX for the hot list case, tuple fallback,
  duplicate-key merge, parallel distinct keys, global attrs, data dicts,
  dictable-third-as-data, negative keys, bool keys, int subclasses, node-only
  existing graphs, and non-fresh append.

## Verdict

Rejected. Source was reverted and the previous extension binary was restored.
The next construction pass should not retry the same int-key batch validation
shape; it needs a different primitive that reduces native canonicalization and
graph-storage work rather than only moving the loop across the PyO3 boundary.
