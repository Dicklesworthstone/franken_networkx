# is_biconnected / articulation_points: drop connected_components build + integer adj — FASTER than nx (br-r37-c1-biconidx)

## Problem
is_biconnected called connected_components(graph) (materialising every component as
a Vec<String> of node names) just to check `.len() == 1`, then articulation_points.
And articulation_points' dfs_connectivity_analysis built its adjacency via
neighbors_iter(name) -> index_of.get(name) — an index->name->index String round-trip
+ HashMap probe PER EDGE.

## Levers (both byte-identical)
1. is_biconnected: connectivity via the single-BFS is_connected (a graph has one
   component iff connected) instead of connected_components(..).len() == 1.
2. dfs_connectivity_analysis: borrow the integer CSR rows directly
   (neighbors_indices, same insertion order -> same DFS order) instead of the
   per-edge String round-trip; build the name->index map LAZILY, only when bridges
   exist (a bridgeless graph never pays for it).

## Proof
- Parity vs nx 0/750 (50 seeds x {random,cycle,path,tree,disconnected}) on
  is_biconnected + articulation_points (DFS-discovery ORDER) + bridges (order +
  orientation); string-node + bowtie + K2 + empty edge cases; pytest -k
  biconnected/articulation/bridge 525 passed.
- RELEASE build, n=3000 deg8 (min-of-20): is_biconnected fnx 2.14ms vs nx 3.18ms
  (0.67x, FASTER); articulation_points fnx 2.10ms vs nx 6.01ms (2.9x FASTER);
  bridges (tree) faster too. (The debug `maturin develop` build heavily penalises
  the tight integer DFS — that inflated the earlier sweep ratio; release is the
  fair production comparison.)
