# br-r37-c1-mgisol (CopperCliff): MultiGraph/MultiDiGraph load_centrality via simple-projection + native kernel

## Root cause
`load_centrality`'s native fast path is gated `not G.is_multigraph()`, so multigraphs
fell to the nx delegation (~137ms / **0.43x** at n=200 incl. parallels). Newman's load
centrality (split-equally-among-predecessors over node-SEQUENCE shortest paths) is
unaffected by parallel edges, so multigraph load == load on the simple projection.

## Fix (pure-Python, no Rust)
For unweighted whole-graph (`v is None and cutoff is None and weight is None`)
multigraphs, build the simple projection (Graph/DiGraph; nodes in G order,
`add_edges_from` dedupes parallels, keeps self-loops) and route to the bit-exact
native `_raw_load_centrality` kernel.

## Head-to-head vs NetworkX (min of 6, n=200, 1250 edges incl. parallels)
| type         | before | after  |
|--------------|--------|--------|
| MultiGraph   | 0.43x  | 19.55x |
| MultiDiGraph | ~0.43x | 13.59x |

## Parity
0 mismatches over 600 random MultiGraph/MultiDiGraph (maxdiff 1.67e-16), incl.
parallels / self-loops / isolates + empty/single/2-node edge cases. 2386 centrality
conformance tests pass.
