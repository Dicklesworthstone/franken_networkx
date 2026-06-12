# edge_boundary(data/string/default) — de-delegate in-process + attr-gate

## Lever
edge_boundary with any of data/keys/default set converted the WHOLE graph
fnx->nx (O(V+E) via _call_networkx_for_parity) just to annotate boundary edges
(~13x slower than nx). De-delegated for simple Graph/DiGraph: replicate nx's
edge_boundary in-process over fnx's own adjacency (iterate nset1 in set order,
G[n] neighbours in adjacency order, undirected dedups processed sources) + nx's
membership predicate. Added graph_has_any_attrs gate: when no edge carries a
Python-visible attr (common), data=True is uniformly {} / data=<name> is the
default, skipping per-edge adj[nbr] attr-dict materialization. Multigraph keeps
delegating (keyed edge-view order).

## Correctness (vs nx, identical construction)
768 cases across simple/directed/multi/multidi x nbunch2 {None,set,empty} x
data {False,True,'w','missing'} x default {None,-1}: 16 mismatches, ALL in the
PRE-EXISTING _raw_edge_boundary directed data=False path (untouched by this
change) — BEFORE and AFTER both report exactly 16. Zero NEW divergence. The
in-process path matches nx-on-identically-built graphs, FIXING the old delegated
path's fnx->nx conversion-reorder artifact. golden sha 72bcb59c9185cd7a.
115 boundary/cut_size/volume tests pass; filed br-r37-c1-tep7r for the directed
_raw order bug.

## Benchmark (warm min, interleaved) — ratio = nx/fnx
| scenario               | BEFORE fnx     | AFTER fnx      | self-speedup |
|------------------------|----------------|----------------|--------------|
| BA(200) data=True      | 1.510ms (0.08x)| 0.311ms (0.41x)| 4.9x         |
| BA(500) data=True      | 4.423ms (0.07x)| 0.774ms (0.41x)| 5.7x         |

Gap to nx narrows from ~13x slower to ~2.4x. Residual is the Python iterate-and-
filter floor vs nx's C EdgeDataView (a native edge_boundary_data kernel would
close it). attr-PRESENT data='weight' stays ~0.29x (per-edge AtlasView access).
