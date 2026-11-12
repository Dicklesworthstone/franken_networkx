# Mutation-surface matrix round 3 (noise-immune session: host load 22-35)

## Probed (10 shapes x 4 classes + SubgraphView)
remove_edge multigraph key variants (str/int/missing-key/missing-pair/
no-key-removes-last), clear, clear_edges, remove_node with attrs+edges,
edge-subscript dict.pop, nodes-subscript update, SubgraphView
parent-mutation reflection + frozen-view error parity.

## Result: 1 divergence found and fixed
Multi remove_edge(u, v, key=...) on a MISSING PAIR: nx's
`self._adj[u][v]` KeyError fires BEFORE key handling, so the message
omits the key ("The edge 5-6 is not in the graph."); fnx reported the
key-specific wording for both shapes. Wrapper now distinguishes
missing-pair (key-less message) from present-pair-missing-key.

## Everything else: CLEAN — the mutation-surface arc (rounds 1-3:
add_edges_from/add_edge/remove_*/update/clear/views) is now certified
across all four classes with committed batteries.
