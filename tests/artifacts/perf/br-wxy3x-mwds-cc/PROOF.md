# approximation.min_weighted_dominating_set: de-delegate (1.7x slower -> 1.46x faster)

## Gap
_ApproximationNamespace.__getattr__ delegated to nx, which builds
`neighborhoods = {v: {v}|set(G[v]) for v in G}` over fnx's slow AtlasView and
calls `_cost` -> `G.nodes[v]` per candidate each greedy iteration (plus the
fnx->nx conversion). ~1.7x slower than nx (2.0ms vs 1.3ms ws-120).

## Lever (one, pure-Python — no rebuild)
Concrete _ApproximationNamespace method: snapshot closed neighborhoods via native
to_dict_of_lists (list(G) order, so the `min(neighborhoods.items(), key=_cost)`
tie-break matches nx's insertion order) and run nx's EXACT greedy on local dicts.
Simple Graph fast path; multigraph delegates; directed raises.

## Behavior parity
vs upstream nx: 33 checks (ws Graph x 30 seeds + weighted + empty + multigraph),
0 mismatches. Directed raises NetworkXNotImplemented.

## Speed (ws-120, min-of-N)
1.7x slower -> 1.46x FASTER than nx (1.96ms -> 0.90ms = 2.14x self-speedup).
