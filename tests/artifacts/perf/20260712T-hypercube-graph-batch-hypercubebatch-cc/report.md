# br-r37-c1-hypercubebatch — hypercube_graph INDEX-pair edge batch-insert

Status: **SHIP.** 11.55x, byte-identical. My change clippy-clean (crate has pre-existing peer lint debt,
untouched).

## The target

`hypercube_graph(n)` (fnx-algorithms) — the hypercube graph Qₙ: `2ⁿ` nodes (named `"0".."2ⁿ-1"` via
`gen_nodes`), an edge between `i` and `i ^ (1<<bit)` for each bit, emitted once when `j > i` via the per-edge
helper `gen_edge(&mut g, i, j)`.

## The lever — INDEX batch (drops the String conversion, not just the policy record)

`gen_edge(g, i, j)` does `i.to_string()` + `j.to_string()` + `add_edge` (name→index hash + policy record).
Because `gen_nodes` names node `i` exactly `i.to_string()`, node **index** `i` *is* the loop variable `i`.
So collect the edges as `(i, j)` **usize index pairs** and insert with one
`Graph::extend_existing_index_edges_unrecorded` — which skips **both** `to_string()` allocs, the name→index
hashes, and the per-edge policy record. This is the full generator-batch lever, not just the policy-drop
tier: hence 11.55x (vs the String-pair `grid_graph` batch's 2.73x).

## Byte-identical argument

The guard `j > i` reads only the loop vars (never `g`); each `(i, j)` with `j > i` is a unique non-self-loop
edge. `extend_existing_index_edges_unrecorded` dedups on `canon_pair(left_idx, right_idx)` and canonicalizes
`edge_index_endpoints` by node **name** (`left_name <= right_name`) — the identical string comparison
`add_edge` uses (so e.g. nodes `"10"`/`"2"` order the same lexicographically) — and pushes `adj_indices` in
the given order, exactly as the per-edge loop. All nodes are pre-added by `gen_nodes`. Verified: A/B parity
`assert_eq!(edges_ordered_borrowed + nodes_ordered)` on Q13 (8192 nodes, 53248 edges) passed before timing;
suite test `test_hypercube_graph` passes.

## Median A/B (paired-interleaved, one binary, NULL control)

`cargo test --release -p fnx-algorithms --lib hypercube_graph_batch_ab -- --ignored --nocapture`

Q13: 8192 nodes, 53248 edges. 61 rounds. Ratio = base/cand, **>1 = batch faster**.

| row | median | win_rate | p5_p95 |
|-----|-------:|---------:|--------|
| `BATCH_vs_string` | **11.5494x** | 61/61 | [8.8514, 15.9960] |
| `NULL_batch_vs_batch` | 1.0467x | 36/61 | [0.8023, 1.4939] |

Decisive: candidate p5 (8.85) ~5.9x above the NULL p95 (1.49); all 61 rounds won. (The null is a touch wide
because the shared 8192-node `gen_nodes` build adds variance, but the candidate p5 is far above it.)

## Clippy note

My change is clippy-clean (0 findings in production ~33896-33920 / test ~68843-68940, grep-verified). The
crate has 12 pre-existing clippy `-D warnings` errors in peer/committed code — left untouched per
shared-checkout discipline.

## Files

- Production: `crates/fnx-algorithms/src/lib.rs` — `hypercube_graph`.
- Test-only: `hypercube_graph_batch_ab` A/B.

## Vein status

Twenty-second result-builder batch win. **Opens the `gen_edge` index-batch sub-lever:** every generator that
(a) names nodes `"0".."N-1"` via `gen_nodes` and (b) adds edges via `gen_edge(&mut g, i, j)` over integer
indices can collect `(i, j)` index pairs → `extend_existing_index_edges_unrecorded` for the **12x tier**
(drops the `to_string()` too), not the 2.7x String-pair tier. Reachable `gen_edge`-based candidates next:
`complete_bipartite_graph`, `complete_multipartite_graph`, and the classic-generator family.
