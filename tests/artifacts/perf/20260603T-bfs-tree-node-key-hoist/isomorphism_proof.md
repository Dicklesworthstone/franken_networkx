# Isomorphism Proof: Rejected BFS tree node-key hoist

## Change Tested
The candidate only replaced `gr.py_node_key(py, v)` in `bfs_tree` child-node insertion with a hoisted `node_key_map` lookup and the same canonical-string fallback.

## Ordering Preserved
Yes. Traversal edges were computed by the same `fnx_algorithms::bfs_edges*` functions, and result insertion still iterated `edges` in the original order.

## Tie-Breaking Unchanged
Yes. No neighbor iteration, queue discipline, reverse traversal, depth limit, or `sort_neighbors` behavior changed.

## Floating-Point
N/A. `bfs_tree` does not compute floating-point values.

## RNG
Unchanged. Benchmark graph generation used seed `42`; the implementation does not use RNG.

## Golden Output
Baseline FNX SHA: `f9d0aa036915df76522b43e5f2ed9bcb3539215c9278de3f53d07f2c69905abf`

NetworkX SHA: `f9d0aa036915df76522b43e5f2ed9bcb3539215c9278de3f53d07f2c69905abf`

Candidate after SHA: `f9d0aa036915df76522b43e5f2ed9bcb3539215c9278de3f53d07f2c69905abf`

Restored SHA: `f9d0aa036915df76522b43e5f2ed9bcb3539215c9278de3f53d07f2c69905abf`

## Source Restoration
`git diff -- crates/fnx-python/src/algorithms.rs` returned empty after the candidate was removed.
