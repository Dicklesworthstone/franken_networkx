# PERF WIN — MultiDiGraph(DiGraph) native absorb (0.41x -> 1.6-1.9x)

- Agent: `CopperCliff` (cc) · 2026-06-22 · MEASURED · bead `br-r37-c1-mdgdig`
- Files: `crates/fnx-python/src/digraph.rs`, `python/franken_networkx/__init__.py`

## Gap
Broad warm sweep on current origin/main: `MultiDiGraph(<plain DiGraph>)` ran
**0.41-0.53x** vs nx (36.7ms vs 15.2ms @ n=2000/m=8000). `MultiDiGraph(MultiDiGraph)`
and `MultiGraph(Graph)` were already fast — only the DiGraph->MultiDiGraph
conversion lacked a native absorb. `_copy_constructor_graph_source` fell to the
general Python replay: `clear()` + `add_nodes_from` + `add_edges_from(4-tuples)`.

## Negative evidence (Python ruled out)
Profiled: `add_edges_from` alone = 28.5ms of 41.6ms. Tested every edge-tuple
shape — `(u,v,0,dict)`, `(u,v,dict)`, bare `(u,v)`, precomputed list — ALL ~29-32ms.
The cost is inherent to `MultiDiGraph.add_edges_from` keyed insertion, NOT the
per-edge `dict()` copies. No pure-Python route closes the gap.

## Fix
Added `absorb_digraph_keyed_from_digraph` to `impl PyMultiDiGraph` (directional
analog of the existing `absorb_graph_bidirected_from_graph` for Graph sources):
builds the MultiDiGraph inner directly from the DiGraph inner in one pass —
node-major `successors` order, key 0 per edge, shallow-copied attrs, graph attrs
preserved. Wholesale-replaces self's state (the same clear()+rebuild the replay
did). Returns `Ok(false)` (fall through to Python replay) on mixed-display rows
(`succ_py_keys`/`pred_py_keys` non-empty) or `__fnx_incompatible` attrs. Wired in
`_copy_constructor_graph_source` next to the Graph-source absorbs.

## Parity (byte-exact)
- 6 hand shapes (plain/attrs/self-loops/str-keys/empty/graph-attrs) + 60 randomized
  (n<=60, m<=200, random attrs): 0 mismatches. Verified node order, node data,
  `edges(keys=True,data=True)` order, succ AND pred adjacency, graph-level attrs.
- Shallow-copy semantics: `M[u][v][0] is not src[u][v]`, `== src[u][v]`, and
  mutating the copy does NOT mutate the source.

## Perf (warm min-of-9, vendored nx 3.6.1)
```
  n=500  m=2000 : fnx 1.90ms  nx 3.60ms   1.90x
  n=2000 m=8000 : fnx 8.24ms  nx 15.48ms  1.88x   (was 0.41x; ~4.5x self-speedup)
  n=5000 m=20000: fnx 28.6ms  nx 46.4ms   1.62x
```

## Conformance
Full suite: zero new failures vs origin/main baseline (49222 passed). The 5
pre-existing origin failures (pagerank-non-string-weight, gexf classification,
waxman seed, 2x coverage-matrix-doc) are unrelated — proven identical with the
`__init__` wiring reverted (absorb dormant). `test_constructor_absorb_conformance_guard`
and 2292 targeted MDG/convert/construct tests pass.
