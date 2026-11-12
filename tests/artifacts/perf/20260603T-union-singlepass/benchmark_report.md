# union: single-pass attributed construction (correctness fix + ~4x)

Lever: union built via native `_raw_union` (drops ALL attributes, returns an
undirected Graph) + `_rebuild_operator_output` + a `_copy_attrs_into` walk that
re-queried both inputs per node/edge via `has_edge` / `__getitem__`. Replace the
three passes with ONE attributed construction pass: `cls()` + graph-attr merge +
`add_nodes_from(data=True)` x2 + `add_edges_from(data=True)` x2 (keys for
multigraphs). Node sets are disjoint (union's contract), so no overlap handling
is needed.

CORRECTNESS FIX: the old pipeline dropped the graph-level attribute dict
entirely — `union(G, H).graph == {}` instead of nx's merged
`{**G.graph, **H.graph}` (later graph wins on key clash). Node/edge attrs were
already preserved; graph attrs were silently lost. (compose / union_all /
disjoint_union were already correct — only `union` had this bug.)

## Benchmark (two watts_strogatz(150,4) graphs, median of 10)

| impl        | time     |
|-------------|----------|
| nx          | 0.60 ms  |
| fnx BEFORE  | 14.43 ms |
| fnx AFTER   | 3.63 ms  |

Self-speedup ~4x; gap 11.3x-slower -> 6.5x. Residual is the construction tax
(add_*_from), tracked by br-r37-c1-w1dm8.

## Isomorphism + golden proof

Union (graph attrs, nodes+attrs, edges+attrs, keys) byte-identical to nx across
Graph / DiGraph / MultiGraph / MultiDiGraph; rename path; non-disjoint
NetworkXError; directed/undirected type-mismatch NetworkXError; graph-attr
H-wins-on-overlap (test_union_singlepass_parity, 5 cases). 250 existing
union/operator tests pass.

GOLDEN sha256 of union signature (two watts_strogatz(40,4)):
be2fae4d3a2ea531b73ade82... (nx == fnx).
