# is_negatively_weighted — scan via to_dict_of_dicts kernel, not edges(data=True)

## Lever
is_negatively_weighted's whole-graph branch did
`any(weight in data and data[weight] < 0 for _,_,data in G.edges(data=True))` —
paying the per-edge edges(data=True) materialization tax (~2x slower than nx).
Route the scan through the native to_dict_of_dicts kernel ({u: {v: live_edge_dict}}
built in Rust) which reflects Python-overlay attr mutations and avoids the
per-edge view walk. The native edge-weight bindings
(_fnx.graph_has_negative_edge_weight) CANNOT be used — they read the Rust inner
AttrMap and MISS attrs set via G[u][v][k]=v post-creation (verified: returns
False for a post-creation negative weight). Multigraph / views keep edges() scan.

## Correctness
60 cases (directed + undirected x weight modes {int,neg-int,missing,float,
alt-attr} x weight {weight,cost,None} x edge= form x post-creation mutation):
0 mismatches vs nx. golden b6f8d375. 1270 negative/weighted tests pass.

## Benchmark (warm min, interleaved before/after)
| graph              | BEFORE    | AFTER    | self-speedup |
|--------------------|-----------|----------|--------------|
| undirected BA(300) | 0.4524ms  | 0.1681ms | 2.69x        |
| directed gnp(300)  | 1.3546ms  | 0.6234ms | 2.17x        |

Flips 0.49x slower -> ~1.3x FASTER than nx. Generalizes the "whole-graph
per-edge scan -> to_dict_of_dicts native rows" lever (same kernel as adjacency /
edge_boundary). Native weight bindings are overlay-unsafe; to_dict_of_dicts reads
edge_py_attrs so it stays correct.
