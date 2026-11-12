# br-r37-c1-windmillbatch — windmill_graph INDEX-pair edge batch-insert

Status: **SHIP.** 17.90x, byte-identical. My change clippy-clean (crate has pre-existing peer lint debt,
untouched).

## The target

`windmill_graph(k, n)` (fnx-algorithms) = the windmill graph Wd(k,n): `n` copies of Kₖ sharing a universal
center (node 0), `1 + n·(k-1)` nodes total (named `"0".."total-1"` via `gen_nodes`). Two per-edge phases per
copy: center→copy edges (`gen_edge(0, i)`) and the within-copy clique (`gen_edge(i, j)`).

## The lever — INDEX batch (the `gen_edge` sub-lever)

Node index `i` *is* the loop variable. Collect all edges (per copy: center→copy, then within-copy clique;
same order) as `(i, j)` **usize index pairs** and insert with one
`Graph::extend_existing_index_edges_unrecorded` — dropping both `to_string()` allocs, the name→index hashes,
and the per-edge policy record.

## Byte-identical argument

Every center edge is `(0, i)` with `i ≥ 1 > 0`, and every clique edge is `(i, j)` with `i < j` — all unique,
no self-loops; the loops read only their own vars (never `g`). `extend_existing_index_edges_unrecorded`
dedups on `canon_pair`, canonicalizes `edge_index_endpoints` by node **name** (identical string comparison to
`add_edge` — e.g. `"0"` sorts before every positive index's label), and pushes `adj_indices` in the given
order, exactly as the per-edge loop. All nodes are pre-added by `gen_nodes`. Verified: A/B parity `assert_eq!
(edges_ordered_borrowed + nodes_ordered)` on Wd(100,15) (1486 nodes, ~74250 edges) passed before timing;
suite test `test_windmill_graph` passes.

## Median A/B (paired-interleaved, one binary, NULL control)

`cargo test --release -p fnx-algorithms --lib windmill_graph_batch_ab -- --ignored --nocapture`

Wd(100,15): 1486 nodes, ~74250 edges. 61 rounds. Ratio = base/cand, **>1 = batch faster**.

| row | median | win_rate | p5_p95 |
|-----|-------:|---------:|--------|
| `BATCH_vs_string` | **17.9007x** | 61/61 | [12.5003, 22.3953] |
| `NULL_batch_vs_batch` | 1.0141x | 32/61 | [0.8555, 1.1657] |

Decisive: candidate p5 (12.50) ~10.7x above the NULL p95 (1.17); all 61 rounds won. (Between hypercube's
11.55x and bipartite's 31.65x: the 1486-node `gen_nodes` build — common to both arms — is a larger share than
bipartite's 300 nodes, diluting the index-batch's edge-loop win.)

## Clippy note

My change is clippy-clean (0 findings in production ~33883-33902 / test ~69279-69382, grep-verified). The
crate has 12 pre-existing clippy `-D warnings` errors in peer/committed code — left untouched per
shared-checkout discipline.

## Files

- Production: `crates/fnx-algorithms/src/lib.rs` — `windmill_graph`.
- Test-only: `windmill_graph_batch_ab` A/B.

## Vein status

Twenty-sixth result-builder batch win; 6th in the `gen_edge` index-batch gold seam (hypercube 11.55x,
multipartite 28.34x, bipartite 31.65x, turan 25.42x, windmill 17.90x). Next reachable `gen_edge` generators:
`circular_ladder_graph`, `ladder_graph`, `wheel_graph` (sparser → smaller wins), `balanced_tree` (tree).
