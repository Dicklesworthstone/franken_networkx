# all_triads: direct construction instead of per-triad subgraph().copy()

Lever: `all_triads` yielded each 3-node induced subgraph via
`G.subgraph([i, j, k]).copy()` — routing C(|V|,3) times through fnx's
filtered-view + materialize-copy machinery, which carries heavy per-call
overhead beyond plain construction. Snapshot G's node/edge/graph attributes
once and build each triad directly with `DiGraph()` + add_nodes_from /
add_edges_from over the induced edges. Same nodes, induced edges, and
node/edge/graph attribute copies; independent attr dicts per triad (no
aliasing).

Unlike complete_to_chordal_graph (where nx used a zero-copy view and fnx had
added a copy), networkx's all_triads ALSO does `.copy()` per triad — so this
gap was construction-tax-bounded (~6x), not catastrophic. The win comes from
direct construction being far cheaper than fnx's subgraph-view copy.

## Benchmark (gnm(40, 200, directed), median of 3, full list())

| impl              | time      |
|-------------------|-----------|
| nx                | 293.0 ms  |
| fnx BEFORE        | ~1960 ms  |
| fnx AFTER         | 149.9 ms  |

Self-speedup: ~13x. Gap vs nx: ~6x-slower -> 0.45x (2.2x FASTER than nx).

## Isomorphism + golden proof

Yielded triads (nodes, induced edges, and node/edge/graph attribute values)
byte-identical to networkx across 7 shapes (attributed/unattributed, dense,
sparse, edgeless, n<3, exactly 3); undirected input raises
NetworkXNotImplemented; mutating a yielded triad does not affect the source
(independent copies); count == C(n,3)
(test_all_triads_direct_parity, 4 cases). 18 existing triad tests pass.

GOLDEN sha256 of all triad signatures (gnm(30, 200, attributed, seed=99)):
297f12708be6fba7d4f2cfb0... (nx == fnx).
