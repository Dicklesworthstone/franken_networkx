# br-r37-c1-mgisol (CopperCliff): MultiGraph average_degree_connectivity fast path

## Root cause
The unweighted-undirected fast path was gated to plain Graph
(`_raw_neighbors_dispatch(G) is not None` excludes Multi), so multigraphs fell to the
per-node AtlasView fallback (~13.6ms / **0.11x** vs nx at n=200).

## Fix (pure-Python)
nx sums over DISTINCT neighbors (G.neighbors yields each once) weighted by MULTI
degree. So: multi-degree from native `G.degree()`, distinct neighbor pairs from the
cheap simple projection's edges, accumulate both directions per edge. Per-node bucket
init mirrors nx's `dsum[k] += s` for every node (degree-0/isolated nodes keep their
bucket).

## Head-to-head (n=200, 1100 edges incl. parallels)
nx 1.57ms, fnx 13.57ms -> **1.33ms** : 0.11x -> **1.18x** (~10x self-speedup)

## Parity
0 mismatches over 1200 graphs (MultiGraph + Graph + MultiDiGraph, maxdiff 0.0 —
integer arithmetic), incl. parallels/self-loops/isolates. Graph & MultiDiGraph paths
unchanged. 967 assortativity conformance tests pass.
