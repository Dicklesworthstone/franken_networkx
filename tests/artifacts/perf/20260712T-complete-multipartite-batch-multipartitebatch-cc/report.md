# br-r37-c1-multipartitebatch — complete_multipartite_graph INDEX-pair edge batch-insert

Status: **SHIP.** 28.34x, byte-identical — the biggest result-builder batch win of the session. My change
clippy-clean (crate has pre-existing peer lint debt, untouched).

## The target

`complete_multipartite_graph(block_sizes)` (fnx-algorithms) = K_{n₁,n₂,…}: `total` nodes (named
`"0".."total-1"` via `gen_nodes`), a cross edge between every pair of nodes in **different** blocks, added via
the per-edge helper `gen_edge(&mut g, i, j)`.

## The lever — INDEX batch (the `gen_edge` sub-lever)

`gen_edge(g, i, j)` does `i.to_string()` + `j.to_string()` + `add_edge`. Because `gen_nodes` names node `i`
exactly `i.to_string()`, node **index** `i` *is* the loop variable. Collect the cross-block edges as `(i, j)`
**usize index pairs** and insert with one `Graph::extend_existing_index_edges_unrecorded` — dropping both
`to_string()` allocs, the name→index hashes, and the per-edge policy record.

## Why 28x — the biggest yet

Two multipliers stack: (1) the index-batch removes the `to_string()` work (the 12x-tier lever, cf. hypercube
11.55x), and (2) this graph is **dense with few nodes** — K_{60,60,60,60} is 240 nodes but 21600 edges, so
the shared `gen_nodes` node-build (240 adds) is negligible against the edge loop. With almost no common
overhead left, the edge-loop speedup shows nearly undiluted → 28.34x. (Hypercube was "only" 11.55x because its
8192-node `gen_nodes` build was ~1/6 of the work and common to both arms.)

## Byte-identical argument

Each `(i, j)` has `i < j` (block `bi` precedes `bj` ⇒ `starts[bi] < starts[bj] ≤ j`), so every collected edge
is a unique cross-block pair with no self-loop; the guard reads only the loop vars (never `g`).
`extend_existing_index_edges_unrecorded` dedups on `canon_pair`, canonicalizes `edge_index_endpoints` by node
**name** (identical string comparison to `add_edge`), and pushes `adj_indices` in the given order, exactly as
the per-edge loop. All nodes are pre-added by `gen_nodes`. Verified: A/B parity `assert_eq!
(edges_ordered_borrowed + nodes_ordered)` on K_{60,60,60,60} (240 nodes, 21600 edges) passed before timing;
suite test `test_complete_multipartite_graph` passes.

## Median A/B (paired-interleaved, one binary, NULL control)

`cargo test --release -p fnx-algorithms --lib complete_multipartite_graph_batch_ab -- --ignored --nocapture`

K_{60,60,60,60}: 240 nodes, 21600 edges. 61 rounds. Ratio = base/cand, **>1 = batch faster**.

| row | median | win_rate | p5_p95 |
|-----|-------:|---------:|--------|
| `BATCH_vs_string` | **28.3401x** | 61/61 | [17.4096, 40.6464] |
| `NULL_batch_vs_batch` | 1.0118x | 35/61 | [0.8705, 1.1544] |

Decisive: candidate p5 (17.41) ~15x above the NULL p95 (1.15); all 61 rounds won.

## Clippy note

My change is clippy-clean (0 findings in production ~33939-33956 / test ~68951-69062, grep-verified). The
crate has 12 pre-existing clippy `-D warnings` errors in peer/committed code — left untouched per
shared-checkout discipline.

## Files

- Production: `crates/fnx-algorithms/src/lib.rs` — `complete_multipartite_graph`.
- Test-only: `complete_multipartite_graph_batch_ab` A/B.

## Vein status

Twenty-third result-builder batch win — largest of the session. Confirms the compounding rule: **index-batch
× dense-few-nodes = maximum win**. The `gen_edge` sub-lever remains rich; next reachable `gen_edge`-based
dense builders: `complete_bipartite_graph` (K_{m,n}, also few-nodes/dense), then the classic-generator family.
