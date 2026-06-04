# Native self-loop utilities (number_of_selfloops / selfloop_edges / nodes_with_selfloops)

Bead: `br-selfloopnative`.

## Catastrophe
number_of_selfloops (a HOT internal utility -- 26 call sites, used as a fast-path
guard across the codebase), selfloop_edges (default form, 8 sites) and
nodes_with_selfloops walked slow views: a per-node `has_edge(u, u)` probe or an
AdjacencyView membership scan. number_of_selfloops was ~14x slower than networkx
(0.13ms vs 0.09ms at n=3000), and nodes_with_selfloops did not use the available
native binding at all.

## Lever (one)
Route all three through the native `nodes_with_selfloops_rust` kernel, which scans
the inner graph in O(|V|) and returns the self-loop nodes in networkx's exact
node-iteration order (verified 80/80 incl. shuffled insertion order). For a simple
graph each node has at most one self-loop, so number_of_selfloops is len(...) and
selfloop_edges is `((n, n) for n in ...)`. Multigraphs (self-loop multiplicity)
keep the exact edge-count path. All paths coerce the input first, so SubgraphView
filtering and nx-typed inputs are handled.

## Proof
test_selfloop_native_parity.py (4/4): 120 graphs (simple/multi, directed/undirected,
shuffled node order) -- counts, self-loop edges and node order identical to
networkx; SubgraphView filtering correct; nx-typed input; multigraph multiplicity.

## Benchmark (warm min-of-N)
    number_of_selfloops n=3000:  nx 0.131ms  fnx 0.091ms  (0.70x = FASTER)  [was ~14x slower]
    selfloop_edges:              nx 0.126ms  fnx 0.092ms  (FASTER)
All three now beat networkx, speeding up the 26 + 8 internal call sites too.

## Files
- python/franken_networkx/__init__.py: number_of_selfloops, selfloop_edges,
  nodes_with_selfloops.
