# bipartite color/sets/is_bipartite_node_set — concrete in-process overrides

## Lever
Continuation of br-r37-c1-r175x (degrees): these nx bipartite fns were re-exported
@nx._dispatchable, so calling on an fnx graph round-tripped the WHOLE graph through
_fnx_to_nx per call. Added concrete overrides running nx's exact algorithms
in-process with fnx-native helpers (isolates / is_connected / connected_components /
the local color+sets), no conversion. Error contracts preserved (NetworkXError on
non-bipartite, AmbiguousSolution on disconnected-no-top / duplicate nodes).

## Correctness
On IDENTICALLY-built graphs (same edge sequence) color + sets(no top) match nx
exactly (value AND BFS-order dict keys), 0/15 mismatches. (Rebuild-from-B.edges()
changes adjacency order -> different valid BFS traversal order, a benchmark
artifact, not a bug.) golden (identical-build) captured. 441 bipartite tests pass.

## Benchmark (warm min, interleaved before/after) — ratio nx/fnx
| op                  | BEFORE    | AFTER    | self-speedup | vs nx    |
|---------------------|-----------|----------|--------------|----------|
| sets(top_nodes)     | 0.6213ms  | 0.0028ms | 222x         | 1.45x FASTER |
| color               | 0.7736ms  | 0.1520ms | 5.1x         | 0.49x (BFS iter floor) |
| is_bipartite_node_set| 1.8068ms | 1.1281ms | 1.6x         |          |

sets flips 142x slower -> 1.45x FASTER. color's residual 2x is the per-neighbor
G.neighbors() PyO3 iteration in the BFS (vs nx's pure-Python dict walk).
