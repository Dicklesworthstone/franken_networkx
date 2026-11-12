# perf: minimum_node_cut(s,t) — native min-cut on node-split auxiliary

Follow-on to minimum_edge_cut (4e95d3c4f). minimum_node_cut delegated everything to nx
(1.49x slower than nx, growing with n).

## Lever (ONE)
The LOCAL (s,t) case: nx's minimum_st_node_cut builds an ALL-UNIT-CAPACITY node-split
auxiliary (each node v -> vA,vB with arc vA->vB; each edge (u,v) -> uB->vA and, undirected,
vB->uA), runs an edmonds-karp min-cut from sB to tA, and maps the cut arcs back to nodes.
fnx's native min-cut binding reproduces nx's edmonds-karp residual byte-for-byte. Build the
same auxiliary WITHOUT explicit caps (a sentinel attr forces unit capacities — fast
construction, no per-edge dicts), take the residual partition, rebuild the auxiliary edge
cut and map (vA/vB -> v), minus {s,t}. Byte-identical to nx, no graph conversion.

## Proof (byte-exact)
- Golden node-cut (exact node set) over 73 graphs (gnp undirected+directed, icosahedral,
  karate, complete) x sampled (s,t) == nx for every case:
  dd36774b2369c0f167fbb91952a3929480d045875b91d4ac3fd15f3906d7427a
- Separately: 144 undirected (incl 28 adjacent s,t -> empty cut) + 120 directed trials,
  0 failures. Error contracts (both-or-neither, node-not-in-graph) match nx. Adjacent
  endpoints return empty set (nx contract). 786 connectivity tests pass.

## Benchmark (connected_watts_strogatz, min-of-8)
| n    | nx (ms) | fnx before | fnx after | before vs nx | after vs nx |
|------|---------|------------|-----------|--------------|-------------|
| 800  | 42.8    | ~77 (1.5x) | 14.99     | 1.49x slower | 2.86x FASTER|
| 1500 | 106.1   | ~91 (?)    | 37.21     | 1.5x slower  | 2.85x FASTER|

1.49x slower -> 2.85-2.86x FASTER than nx. Byte-exact, pure-Python (reuses the native
min-cut partition + sentinel unit caps). GLOBAL (no s,t)/multigraph/flow_func stay delegated.
