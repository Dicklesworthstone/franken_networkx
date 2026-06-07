# all-int cache + per-path int-type propagation (d58s8 session)

## Lever: revision-keyed all-int memo
graph_edge_weights_all_int pre-scan = 21ms/call (equal to the dijkstra
kernel) walking every edge attr per call; pure fn of (revision, attr).
Added all_int_cache (Arc<RwLock<Option<(u64, String, bool)>>>) to Graph
+ DiGraph with edge_weights_all_int() methods; algorithms fns delegate.
Invalidation proven via G[u][v][k]=v mutation battery (revision bumps).
dijkstra_len wall 8.38 -> 6.47ms loaded.

## Parity bug found BY the typed battery: srczero family (pre-existing)
nx never coerces distance types — each distance's TYPE follows the
Python sum along its chosen path (int+int=int; any float taints; source
= literal int 0). fnx blanket-coerced only the all-int case, so MIXED
graphs returned floats where nx returns ints (e.g. path 1+2=int 3 in a
graph that also has 2.5 weights). Fixed via _sp_propagate_int_types
(per-path re-derivation; the kernel reproduces nx's traversal so the
returned path IS nx's path) wired into single_source_dijkstra,
single_source_bellman_ford(+_path_length), multi_source_dijkstra.

## Residual (filed separately): key-ORDER on equal-distance ties
multi_source + one bellman shape diverge in dict KEY ORDER only
(values+types match) — kernel emission order vs nx push-seq tie-break;
k9q6q-class treatment needed for the multi-source kernel. Filed.
