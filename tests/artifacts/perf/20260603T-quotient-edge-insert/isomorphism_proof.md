# Isomorphism proof: quotient edge insertion

## Scope

Only the simple undirected default quotient path changes. The path is active when:

- `edge_relation is None`
- `edge_data is None`
- `create_using is None`
- `G` is not directed
- `G` is not a multigraph
- default edge weights are integer-compatible

All other paths keep their previous code.

## Ordering

The old code iterated:

1. `i, block_u` from `enumerate(partition)`
2. `j` from `range(i + 1, len(partition))`
3. present `(i, j)` bucket keys only

The new code uses the same loop and appends edge tuples in that exact order before calling `H.add_edges_from(edge_bunch)`. Edge insertion order and tie exposure are unchanged.

## Attributes

For weighted default edges, each tuple contains a fresh `{weight: total}` dict with the same `default_pair_totals[(i, j)]` value the old `H.add_edge(..., **{weight: total})` call used. For `weight` falsey, the tuple is `(block_u, block_v)`, matching the old bare `H.add_edge(block_u, block_v)`.

Node data is unchanged. The live `graph` attribute still stores `G.subgraph(block)`, and `nnodes`, `nedges`, and `density` still come from the partition-local counts added in the prior pass.

## Floating point and RNG

This edge-insertion lever does not alter RNG use in the benchmark graph generator. It also does not change density arithmetic, weight accumulation, or any floating-point path.

## Golden

Baseline, NetworkX, after, and confirm outputs kept the same quotient digest:

`3b82f51eccda8bd9a2f0a24657abf67f8bb2bc9b9da8e49d136f6089b31be62a`

