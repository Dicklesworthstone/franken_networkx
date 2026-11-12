# Isomorphism Proof: br-r37-c1-hbv0y

## Change

`fnx_algorithms::shortest_path_length` now runs unweighted BFS over node indices with a dense distance vector instead of `HashMap<&str, usize>`.

## Ordering

N/A for observable output. The public API returns a scalar path length. Internally, neighbor scan order is unchanged because `neighbors_indices` mirrors graph insertion-order adjacency.

## Tie-Breaking

N/A for observable output. Multiple shortest paths with the same length all produce the same scalar distance.

## Floating Point

N/A. The changed path is unweighted and integer-valued.

## RNG

N/A. No random state is read or advanced.

## Errors

Preserved. Missing source/target validation remains in the PyO3 wrapper. Missing/no-path kernel results still return `length: None`, and the wrapper raises the same `NetworkXNoPath` message for no path.

## Witness

The complexity witness remains `bfs_shortest_path_length` with the same `O(|V| + |E|)` claim. `nodes_touched`, `edges_scanned`, and `queue_peak` preserve the same counting semantics using dense state.

## Golden Outputs

Baseline fnx, after fnx, and NetworkX all report:

`3d95e61519c778f79f1a76ab3f900fb9c8e7a3fb2991e89213fba2475aec3547`
