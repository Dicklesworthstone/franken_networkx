# Perf win — cytoscape_graph batch construction (br-r37-c1-cytobatch)

- Agent: `BlackThrush` · 2026-06-20 · File: `python/franken_networkx/__init__.py`

cytoscape_graph rebuilt from Cytoscape.js JSON via per-node `add_node` +
`nodes[node].update` AND per-edge `add_edge` + `edges[s,t].update` — 4 PyO3 view
crossings per element, 0.27x nx (29ms vs 7ms on 1000/4000).

Lever: collect (node, data) and (source, target, data) tuples, then build via
`add_nodes_from` / `add_edges_from` in one batch. Simple Graph/DiGraph only; the
multigraph path keeps `_add_json_multiedge` (keyed parallel edges).

## vs NetworkX 3.6.1 (pinned taskset -c 2, warm min-of-15, 1000n/4000e)

| cytoscape_graph(data) | before | after |
| --- | ---: | ---: |
| | 0.27x (29ms) | **1.26x** (3.35ms) — 7.8x self |

## Parity

600 random round-trips across Graph/DiGraph/MultiGraph/MultiDiGraph with node +
edge attrs: 0 mismatches (node order, edges, node/edge attrs, graph attrs, type).
pytest -k 'cytoscape or json' 32 passed.
