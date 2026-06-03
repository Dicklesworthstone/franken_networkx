# report_to_pygraph edge-attr conversion lever (br-r37-c1-lcw4j)

## Change
`report_to_pygraph` (the shared Rust-Graph -> PyGraph conversion used by every
undirected generator: complete/BA/watts/grid/path/star/cycle/...) populated
`edge_py_attrs` by iterating `inner.edges_ordered()`.

`edges_ordered()` builds a `Vec<EdgeSnapshot>` that, per edge, clones the left
String, the right String, AND the full edge `AttrMap`, plus a dedup
`HashSet<EdgeKey>` over all directed adjacency entries. For complete_graph(300)
(44850 edges) that is ~30ms of the ~45ms conversion — and the cloned attrs are
immediately discarded (only empty dicts are created).

New: walk adjacency directly via `nodes_ordered()` x `neighbors_iter()` and
insert one empty `PyDict` per `PyGraph::edge_key(u, v)`.

## Why output is bit-identical
`PyGraph::edge_key(u, v)` canonicalizes by `u <= v`, so the two directed
adjacency entries of an undirected edge collapse to the SAME key; `entry().
or_insert_with()` therefore yields exactly the same key SET that
`edges_ordered()` (one direction per edge) + `edge_key` produced. `edge_py_attrs`
is a `HashMap` (unordered), so its iteration order is not observable. Node maps,
the inner Graph, and EdgeView are untouched, so `G.nodes()`/`G.edges()` order and
`G[u][v]` access are unchanged. Self-loops canonicalize to (u,u) once. No FP, no RNG.

## Verification
generator_parity_golden.py: 8 generators vs networkx, comparing node ORDER,
edge set, node data, edge data — digest unchanged pre/post and equal to nx:

    GEN_GOLDEN 97611327d3562505f27b521936c8d35383d17bdec4f135d8671dce01d5647b52

Plus list(G.edges()) order parity, list(G.nodes()) order parity, and edge/node
attr mutation persistence. 2069 generator pytest cases pass; clippy -D warnings
clean.

## Benchmark (cProfile tottime, noise-stable)
native `_fnx.complete_graph(300)`: 48.2ms -> 31.1ms per call (1.55x).
gen_complete(300) end-to-end gap vs nx: 4.06x -> 2.16x.
Sparse generators (BA/watts/grid) are dominated by their generator kernel, not
this conversion — separate follow-up.

Opportunity Score = Impact 3 x Confidence 5 / Effort 1 = 15.0.
