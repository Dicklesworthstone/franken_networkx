# br-r37-c1-mgisol (CopperCliff): native Multi isolates — drop per-call simple-graph projection

## Root cause
`isolates` / `number_of_isolates` / `is_isolate` bindings dispatched Multi types
through the `_` arm of `GraphRef`, which calls `gr.undirected()` /
`gr.digraph()` — and for `MultiUndirected` / `MultiDirected` those run
`multigraph_to_simple_graph` / `multidigraph_to_simple_digraph`, a FULL O(V+E)
simple-graph rebuild PER CALL (GraphRef is reconstructed by `extract_graph` every
call, so the OnceCell never amortizes). Isolate detection only needs per-node
adjacency-row emptiness, making the whole projection pure waste (~140x slower than
the simple-graph path at n=200).

## Fix
Native isolate methods on `fnx_classes::MultiGraph` (lib.rs) and
`fnx_classes::MultiDiGraph` (digraph.rs): a node is isolated iff its adjacency
row (MG) / both successor+predecessor rows (MDG) are empty/absent. Self-loops put
the node in its own row, so a self-loop node stays NON-isolated — matching nx's
degree-2 self-loop convention. Binding (fnx-python/algorithms.rs) gains explicit
`MultiUndirected`/`MultiDirected` arms; the match is now exhaustive (no `_`), so
no Multi type can silently regress to the projection path again.

## Head-to-head (min of 8, n=200, 1000 edges + parallels + self-loops + 20 isolates)
| function            | type         | before | after   |
|---------------------|--------------|--------|---------|
| number_of_isolates  | MultiGraph   | 0.09x  | 58.66x  |
| isolates            | MultiGraph   | 0.08x  | 19.46x  |
| number_of_isolates  | MultiDiGraph | 0.13x  | 27.06x  |
| isolates            | MultiDiGraph | 0.13x  | 17.32x  |
| is_isolate          | MG / MDG     | ~3x    | ~2.7-2.9x (already Python one-liner) |

## Parity
0 mismatches over 800 random multigraphs (MG + MDG), x3 checks each
(isolates list / number_of_isolates / is_isolate per node), incl. isolates,
self-loops, and parallel edges. 639 + 534 conformance tests pass.
