# br-r37-c1-8e9jf adjacency row-cache lever

Status: rejected.

Profile-backed target: `dict(G.adjacency())` on `connected_watts_strogatz_graph(n=800, k=6, p=0.3, seed=0)` after `br-r37-c1-4b5ie`. The saved cProfile output still routed through `_simple_graph_adjacency -> _fnx.to_dict_of_dicts_undirected`, with residual native time spent copying cached row dictionaries into an outer adjacency snapshot.

Lever tested: return the cached row dictionaries directly from `copy_dict_of_dicts_cache` instead of copying each row.

Benchmark evidence:

- Baseline mean: `0.00009716714688693174s`
- Candidate mean: `0.00003673221886856481s`
- Candidate speedup: `2.645283891904682x`
- Baseline golden SHA256: `e48e74c7624b404732f32f54747686431bde9733cf1e3072d3c61e80eda12e53`
- Candidate golden SHA256: `e48e74c7624b404732f32f54747686431bde9733cf1e3072d3c61e80eda12e53`
- Adjacency output SHA256: `05e5b22eb7a79e6009ddaeb9620bcef89b14f7c3e7bb0f83139b862817d6512b`

Behavior proof:

- Ordering/tie-breaking: benchmark golden serialization preserved node and neighbor order; no algorithm tie-break logic changed.
- Floating point/RNG: no floating-point path changed; graph construction used fixed `seed=0`.
- Edge attribute liveness: preserved for existing edges (`d[u][v] is G[u][v]` and attr mutation is visible).
- Rejection condition: row mutation was not coherent. The candidate made `row["c"] = {...}` visible in later `dict(G.adjacency())` calls, but `G.has_edge("a", "c")` still returned false in FrankenNetworkX. NetworkX returns true because its row is the real `_adj[u]` storage. This is an observable graph-semantics change, so the lever is not accepted.

Next primitive:

Do not retry direct row-reference reuse. The next profile-backed primitive should be a mutation-coherent adjacency materialization design: either live row proxies that route row writes into native graph topology, or a copy-preserving iterator/outer materializer that removes outer-dict overbuild without exposing mutable cached rows.
