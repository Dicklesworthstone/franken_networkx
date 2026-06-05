# br-r37-c1-xh7jk Isomorphism Proof

## Claim

The one-lever change preserves NetworkX-observable `Graph.remove_nodes_from` behavior while replacing repeated per-node index rebuilds with one batch compaction pass for exact `Graph`.

## Ordering

- Node survivor order is preserved by retaining entries in the existing `IndexMap` storage order.
- Adjacency survivor order is preserved by retaining each existing neighbor map and filtering removed endpoints without sorting.
- Edge iteration order is preserved by retaining entries in `edges_storage_order` and rebuilding `edge_index_endpoints` from that retained order.
- The Rust unit test `remove_nodes_from_matches_repeated_removal_and_rebuilds_indices` compares batch removal to repeated `remove_node` and verifies rebuilt neighbor and edge indexes resolve to the same ordered nodes.

## Tie-Breaking

- No traversal, shortest-path, or edge-selection tie-break policy changes.
- Duplicate removal inputs collapse to a set of present canonical nodes, matching NetworkX's ignore-missing and idempotent bunch-removal behavior.
- The Python wrapper still materializes and hash-checks the iterable before entering the native method, preserving generator-reading and unhashable-input behavior.

## Attributes

- Python node attributes are removed only for nodes that were present in the graph.
- Python edge attribute dictionaries are removed only when either endpoint is in the present removal set.
- Surviving edge and node attribute dictionaries keep their existing object identity.

## Floating Point And RNG

- Not applicable. The operation performs no floating-point arithmetic and consumes no randomness.

## Golden Evidence

- Baseline golden SHA: `357f32eeb2db2d1b6441a251503b5efc8af2cebc121234caeb7b60dbfa7580e2`
- After golden SHA: `357f32eeb2db2d1b6441a251503b5efc8af2cebc121234caeb7b60dbfa7580e2`
- After timed-section digest: `ef9cdaf4ea778286cb601d98557fa93c7e2e28c14da637043fac6cd7daf4f77f`
- The golden covers `range`, `list`, and `tuple` removal bunches and compares FNX vs NetworkX nodes, edges with attrs, degree view, node count, and edge count.

## Fallback Trigger

If later parity tests find mismatched survivor ordering, missing-node behavior, Python attr identity, or cache/index rebuild behavior, the exact `Graph.remove_nodes_from` binding can route back to the prior per-node loop while leaving the Rust batch helper isolated.
