# Alien Primitive Recommendation

## Target

`quotient_graph(Graph, partition)` default node-data construction after
`br-r37-c1-f9gp2`.

## Profile Evidence

Baseline cProfile showed repeated filtered-view counting as the dominant
remaining cost:

- `_default_node_data`: `8.809s`
- filtered `number_of_edges`: `12.083s`
- filtered `number_of_nodes`: `5.552s`
- `density`: `4.383s`
- `_node_visible`: `13.719s`
- `_from_nx_graph`: `4.872s`

## Primitive

Partition-local sufficient statistics:

- Build immutable node-to-block metadata once.
- Scan source edges once.
- Derive per-block `nnodes`, `nedges`, and `density` from counts.
- Reuse the same scan for default simple-undirected cross-block edge weights.
- Construct the fnx quotient result directly when `create_using is None`.

## Graveyard Match

- Incremental computation / "only recompute changed subgraphs": replace repeated
  full subgraph scans with one aggregate pass over the changed partition state.
- Deterministic partition metadata: keep node-to-block mapping immutable during
  the quotient construction.
- Constants-kill-you countermeasure: choose flat dict/list aggregates over a
  heavier asymptotic data structure because this workload is well below the
  crossover where exotic structures pay.

## Score

Impact 5 x Confidence 5 / Effort 2 = 12.5.

## Fallback

The existing custom `edge_relation`, custom `edge_data`, explicit
`create_using`, directed edge construction, multigraph edge construction, and
non-integer weight fallback paths remain available. The direct result return is
limited to `create_using is None`.
