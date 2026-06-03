# Alien recommendation: quotient edge insertion boundary

## Profile signal

After the quotient node-metrics pass, `quotient_graph` moved from node-data construction to result edge insertion:

- `quotient_graph`: `0.118s`
- `_add_default_undirected_bucketed_edges`: `0.074s`
- `H.add_edge` calls: `0.105s` cumulative across graph build plus quotient result insertion

## Primitive

Use the narrow-interface batching primitive: accumulate internally generated, already validated edge tuples in NetworkX block-pair order and cross the graph mutation boundary once.

This is not a public API change. Public `Graph.add_edges_from` validation remains unchanged.

## Lever

For the simple undirected default quotient path:

1. Preserve the existing nested `partition[i], partition[j]` iteration order.
2. Append `(block_u, block_v, {weight: total})` or `(block_u, block_v)` tuples.
3. Call `H.add_edges_from(edge_bunch)` once.

Fallback paths for custom `edge_relation`, custom `edge_data`, directed graphs, multigraphs, explicit `create_using`, and unsupported non-integer default weights remain unchanged.

## Score

Impact 2 x Confidence 3 / Effort 1 = `6.0`.

