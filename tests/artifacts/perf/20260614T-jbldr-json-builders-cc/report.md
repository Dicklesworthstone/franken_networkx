# adjacency_graph / node_link_graph — batch json->graph construction (4.3x / 1.9x self)

Agent: cc · 2026-06-14

## Problem
Both json->graph builders constructed the graph one element at a time:
per-node add_node(**data) + (adjacency_graph) graph.nodes[n].update, and per-edge
add_edge(u,v,**data) + graph[u][v].update. Each call pays the PyO3-boundary +
adjacency-view __getitem__ + ledger cost once per node/edge — adjacency_graph
~4.3x nx, node_link_graph ~2.0x nx.

## Fix (one lever — batch the simple-graph path)
Accumulate (node, attrs) and (u, v, attrs) tuples and commit with one
add_nodes_from + one add_edges_from. Same insertion order, and add_edges_from
merges the per-edge attr dict into the edge exactly like the old .update /
add_edge(**data), so output is byte-identical. The multigraph path keeps the
per-edge key-aware _add_json_multiedge.

## Proof
- Golden sha (fnx node+edge+graph data) unchanged AND == nx, undir+dir, with
  node + edge + graph attrs: adjacency_graph 147e0c27d13ed27e / 6ec2a5a13143aeef;
  node_link_graph 78f631bed82e717a / 4a13d63a5fdd5a53. isolated-node + graph-attr
  case verified.
- 65 adjacency_graph/node_link/json conformance tests pass.

## Numbers (warm min, n=600/3000)
- adjacency_graph: 4.33x slower -> 0.99x (now parity/faster; ~4.3x self)
- node_link_graph: 2.00x slower -> 1.07x (~1.9x self)
Pure-Python (__init__.py); no native rebuild.
