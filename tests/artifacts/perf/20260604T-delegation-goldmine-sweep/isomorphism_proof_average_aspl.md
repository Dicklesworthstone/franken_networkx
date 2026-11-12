# Weighted Average Shortest Path Length Distance-Only Dijkstra

Bead: `br-r37-c1-7yg09`

## Profile Target

- Shifted sweep found `average_shortest_path_length_weighted` with matching FNX/NetworkX digest.
- Scaled 500-node weighted-path baseline:
  - Original pre-rebuild FNX mean: `2.323734s`.
  - Restored/current FNX mean: `9.082556s`.
  - NetworkX mean: `0.258559s`.
  - Golden digest: `a00e20c5a9b349e391be6973b0910daeb862788c833cde0d00a914a6e509ed08`.
- cProfile placed the target time inside native `_fnx.average_shortest_path_length`.

## Rejected Micro-Lever

Removing the per-source `HashMap` collection in `fnx-python` preserved the digest but regressed the target to `9.492056s`. That source hunk was restored.

## Kept Lever

Undirected `single_source_dijkstra_path_length` previously called `single_source_dijkstra_full`, which built both distances and full node paths. The distance-only API now extracts the already ordered `multi_source_dijkstra` distance entries directly:

```rust
let result = multi_source_dijkstra(graph, &[source], weight_attr);
result
    .distances
    .into_iter()
    .map(|entry| (entry.node, entry.distance))
    .collect()
```

## Behavior Invariants

- Distance finalize order is preserved because `multi_source_dijkstra.distances` is already in heap-pop/finalize order.
- Path-returning APIs still use `single_source_dijkstra_full`; no path materialization behavior changes there.
- Directed distance-only behavior is unchanged; it already used a distance-only kernel.
- Floating-point values and summation order for ASPL are preserved: each source still returns the same ordered distance vector, and the Python binding still sums per-source distances in source order.
- Error behavior is unchanged: missing source still yields an empty distance vector; disconnected ASPL detection still checks returned distance count against node count.
- RNG is not touched.

## Results

- Confirmed FNX mean: `9.082556s -> 1.155634s` (`7.86x`) against the restored/current baseline.
- Conservative comparison against the earlier pre-rebuild baseline: `2.323734s -> 1.155634s` (`2.01x`).
- After ratio vs NetworkX: `4.481x`.
- Golden digest stayed `a00e20c5a9b349e391be6973b0910daeb862788c833cde0d00a914a6e509ed08`.
- After hyperfine process envelope: `1.489s +/- 0.051s`.
- After cProfile native section: `1.206s/call`.

## Score

Impact `4` x Confidence `5` / Effort `1` = `20.0`; keep.
