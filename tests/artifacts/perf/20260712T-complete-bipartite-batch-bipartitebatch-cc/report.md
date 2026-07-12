# br-r37-c1-bipartitebatch — complete_bipartite_graph INDEX-pair edge batch-insert

Status: **SHIP.** 31.65x, byte-identical — new session record. My change clippy-clean (crate has pre-existing
peer lint debt, untouched).

## The target

`complete_bipartite_graph(n1, n2)` (fnx-algorithms) = K_{n1,n2}: `n1+n2` nodes (named `"0".."n1+n2-1"` via
`gen_nodes`), a cross edge between every left node `i∈[0,n1)` and right node `j∈[n1,n1+n2)`, added via the
per-edge helper `gen_edge(&mut g, i, j)`.

## The lever — INDEX batch (the `gen_edge` sub-lever)

Node index `i` *is* the loop variable (`gen_nodes` names node `i` = `i.to_string()`). Collect the cross edges
as `(i, j)` **usize index pairs** and insert with one `Graph::extend_existing_index_edges_unrecorded` —
dropping both `to_string()` allocs, the name→index hashes, and the per-edge policy record.

## Byte-identical argument

`i < n1 ≤ j`, so every collected `(i, j)` is a unique cross pair with no self-loop; the loop reads only its
own vars (never `g`). `extend_existing_index_edges_unrecorded` dedups on `canon_pair`, canonicalizes
`edge_index_endpoints` by node **name** (identical string comparison to `add_edge`), and pushes `adj_indices`
in the given order, exactly as the per-edge loop. All nodes are pre-added by `gen_nodes`. Verified: A/B parity
`assert_eq!(edges_ordered_borrowed + nodes_ordered)` on K_{150,150} (300 nodes, 22500 edges) passed before
timing; suite test `test_complete_bipartite_graph` passes.

## Why 31.65x — new record

The compounding rule at its extreme: (1) the index-batch removes the `to_string()` work (12x tier), and
(2) K_{150,150} is maximally dense-few-nodes — 300 nodes but 22500 edges (avg degree 150), so the shared
`gen_nodes` build (300 adds) is negligible against the edge loop. Even denser per-node than
`complete_multipartite` K_{60,60,60,60} (28.34x), hence the record.

## Median A/B (paired-interleaved, one binary, NULL control)

`cargo test --release -p fnx-algorithms --lib complete_bipartite_graph_batch_ab -- --ignored --nocapture`

K_{150,150}: 300 nodes, 22500 edges. 61 rounds. Ratio = base/cand, **>1 = batch faster**.

| row | median | win_rate | p5_p95 |
|-----|-------:|---------:|--------|
| `BATCH_vs_string` | **31.6498x** | 61/61 | [22.2190, 43.0384] |
| `NULL_batch_vs_batch` | 0.9919x | 29/61 | [0.7781, 1.2432] |

Decisive: candidate p5 (22.22) ~18x above the NULL p95 (1.24); all 61 rounds won.

## Clippy note

My change is clippy-clean (0 findings in production ~33919-33934 / test ~69073-69163, grep-verified). The
crate has 12 pre-existing clippy `-D warnings` errors in peer/committed code — left untouched per
shared-checkout discipline.

## Files

- Production: `crates/fnx-algorithms/src/lib.rs` — `complete_bipartite_graph`.
- Test-only: `complete_bipartite_graph_batch_ab` A/B.

## Vein status

Twenty-fourth result-builder batch win, new record. The `gen_edge` index-batch sub-lever continues: next the
classic-generator family (`balanced_tree`, `circular_ladder_graph`, `wheel_graph`, `star_graph`, etc.) — all
`gen_nodes`/`gen_edge`-based over integer indices; the denser/fewer-node ones give the biggest wins.
