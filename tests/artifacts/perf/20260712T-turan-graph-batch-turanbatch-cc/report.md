# br-r37-c1-turanbatch — turan_graph INDEX-pair edge batch-insert

Status: **SHIP.** 25.42x, byte-identical. My change clippy-clean (crate has pre-existing peer lint debt,
untouched).

## The target

`turan_graph(n, r)` (fnx-algorithms) = the Turán graph T(n,r): `n` nodes (named `"0".."n-1"` via `gen_nodes`)
partitioned by `i % r`, with an edge between every pair in **different** partitions (`i%r != j%r`), added via
the per-edge helper `gen_edge(&mut g, i, j)`.

## The lever — INDEX batch (the `gen_edge` sub-lever)

Node index `i` *is* the loop variable. Collect the inter-partition edges as `(i, j)` **usize index pairs**
and insert with one `Graph::extend_existing_index_edges_unrecorded` — dropping both `to_string()` allocs, the
name→index hashes, and the per-edge policy record. This combines the cheap-guard property (`i%r != j%r` is
O(1), like kneser) with the index-batch and dense-few-nodes multipliers.

## Byte-identical argument

`j` starts at `i+1`, so every collected `(i, j)` has `i < j` — a unique non-self-loop edge; the guard reads
only the loop vars (never `g`). `extend_existing_index_edges_unrecorded` dedups on `canon_pair`,
canonicalizes `edge_index_endpoints` by node **name** (identical string comparison to `add_edge`), and pushes
`adj_indices` in the given order, exactly as the per-edge loop. All nodes are pre-added by `gen_nodes`.
Verified: A/B parity `assert_eq!(edges_ordered_borrowed + nodes_ordered)` on T(300,5) (300 nodes, 36000
edges) passed before timing; suite test `test_turan_graph` passes.

## Median A/B (paired-interleaved, one binary, NULL control)

`cargo test --release -p fnx-algorithms --lib turan_graph_batch_ab -- --ignored --nocapture`

T(300,5): 300 nodes, 36000 inter-partition edges (avg degree 240). 61 rounds. Ratio = base/cand, **>1 = batch
faster**.

| row | median | win_rate | p5_p95 |
|-----|-------:|---------:|--------|
| `BATCH_vs_string` | **25.4229x** | 61/61 | [17.3829, 31.5429] |
| `NULL_batch_vs_batch` | 0.9975x | 30/61 | [0.8812, 1.1438] |

Decisive: candidate p5 (17.38) ~15x above the NULL p95 (1.14); all 61 rounds won. (A touch below
`complete_bipartite`'s 31.65x because turan's guard loop scans all C(300,2)=44850 pairs — common to both
arms — for 36000 edges, a little more shared overhead.)

## Clippy note

My change is clippy-clean (0 findings in production ~33856-33874 / test ~69174-69268, grep-verified). The
crate has 12 pre-existing clippy `-D warnings` errors in peer/committed code — left untouched per
shared-checkout discipline.

## Files

- Production: `crates/fnx-algorithms/src/lib.rs` — `turan_graph`.
- Test-only: `turan_graph_batch_ab` A/B.

## Vein status

Twenty-fifth result-builder batch win. The `gen_edge` index-batch gold seam continues (5th consecutive:
hypercube 11.55x, multipartite 28.34x, bipartite 31.65x, turan 25.42x). Next reachable `gen_edge`-based
generators: `windmill_graph` (right below turan — center-star + within-copy cliques), `circular_ladder_graph`,
`ladder_graph`, `wheel_graph`.
