# br-r37-c1-y3t0a adjacency iterator lever

Status: rejected.

Profile-backed target: `dict(G.adjacency())` on `connected_watts_strogatz_graph(n=800, k=6, p=0.3, seed=0)`. The baseline profile still routes through `_simple_graph_adjacency -> _fnx.to_dict_of_dicts_undirected`.

Lever tested: return a native copy-preserving iterator over cached adjacency rows, avoiding the throwaway outer dict while still yielding fresh row dict copies.

Benchmark evidence:

- Baseline mean: `0.00009378478488360998s`
- Candidate mean: `0.00011463266093051061s`
- Candidate over baseline: `1.2222948644897307x`
- Effective speedup: `0.8181331927770704x`
- Baseline golden SHA256: `e48e74c7624b404732f32f54747686431bde9733cf1e3072d3c61e80eda12e53`
- Candidate golden SHA256: `e48e74c7624b404732f32f54747686431bde9733cf1e3072d3c61e80eda12e53`
- Adjacency output SHA256: `05e5b22eb7a79e6009ddaeb9620bcef89b14f7c3e7bb0f83139b862817d6512b`

Behavior proof:

- Ordering/tie-breaking: golden adjacency serialization preserved node and neighbor order; no algorithm tie-break logic changed.
- Floating point/RNG: no floating-point path changed; graph construction used fixed `seed=0`.
- Edge attribute liveness: preserved for existing edges (`d[u][v] is G[u][v]` and attr mutation is visible).
- Row mutation isolation: preserved the existing FrankenNetworkX behavior. Mutating a returned row does not affect the next `dict(G.adjacency())` result and `has_edge` remains false.

Rejection:

The candidate preserves behavior but is slower. The per-row PyO3 iterator boundary costs more than the outer-dict overbuild it removes, so no production code was kept.

Next primitive:

Stop iterating the adjacency row-copy family. The next pass should attack a different profile-backed surface with a structural lever, such as conversion/traversal order substrate or a mutation-coherent live adjacency storage design rather than copying cached rows faster.
