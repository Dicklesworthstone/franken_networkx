# get_node_attributes / get_edge_attributes — native attr-presence gate + single-pass

## Lever
get_node_attributes looped per-node ``attrs = G.nodes[node]`` (N separate
Rust->Python attr-dict reconstructions); get_edge_attributes walked
edges(data=True). Two changes:
1. Native ``_fnx.graph_has_any_attrs(G) is False`` short-circuit (~0.08us): when
   no node/edge carries a Python-visible attr — the common "is this optional attr
   (weight/pos/capacity) set?" probe — return {} (default=None) / uniform default
   without any per-item materialization.
2. Replace the per-node loop with nx's single-pass nodes(data=True) comprehension
   (~2.4x cheaper than N x G.nodes[node]).
Gate restricted to ``type(G) in (Graph, DiGraph)`` (graph_has_any_attrs returns
None for multigraphs -> falls through to the correct loop).

## Correctness (byte-exact vs nx)
1200 comparisons across Graph/DiGraph/MultiGraph/MultiDiGraph x attr modes
{none,node,edge,both,partial} x names {w,cap,missing} x default {None,-1,0}:
result dict (value + key ORDER) identical to nx, 0 mismatches. golden sha
5e3146afec1467c9. 921 attribute-referencing tests pass (3 pre-existing unrelated
classification/coverage failures).

## Benchmark (warm min, interleaved before/after) — ratio = nx/fnx
| scenario                  | BEFORE fnx       | AFTER fnx        | self-speedup |
|---------------------------|------------------|------------------|--------------|
| get_node_attrs ABSENT     | 0.353ms (0.25x)  | 0.0033ms (26.6x) | 107x         |
| get_node_attrs PRESENT    | 0.386ms (0.30x)  | 0.165ms (0.70x)  | 2.3x         |
| get_edge_attrs ABSENT     | 1.147ms (0.42x)  | 0.0033ms (146.6x)| 347x         |

ABSENT (the common optional-attr probe) flips from slower-than-nx to 26-147x
FASTER. PRESENT gets 2.3x self-speedup but stays ~0.70x vs nx — bounded by the
nodes(data=True) materialization substrate tax (deeper follow-up).
