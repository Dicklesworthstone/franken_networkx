# br-r37-c1-lollipopbatch — lollipop_graph INDEX-pair edge batch-insert

Status: **SHIP.** 21.28x, byte-identical. My change clippy-clean (crate has pre-existing peer lint debt,
untouched).

## The target

`lollipop_graph(m, n)` (fnx-algorithms) — the lollipop graph: a complete graph Kₘ (the "candy") joined by a
path of `n` nodes (the "stick"), `m+n` nodes total (named `"0".."m+n-1"` via `gen_nodes`). Three per-edge
phases: the Kₘ clique, the clique→path connector, and the path chain — all via `gen_edge(&mut g, i, j)`.

## The lever — INDEX batch (the `gen_edge` sub-lever)

Node index `i` *is* the loop variable. Collect all edges (clique, connector, path; same order) as `(i, j)`
**usize index pairs** and insert with one `Graph::extend_existing_index_edges_unrecorded` — dropping both
`to_string()` allocs, the name→index hashes, and the per-edge policy record. The clique dominates the edge
count, so this is a dense-few-node case.

## Byte-identical argument

Every edge has `source < target` (clique `i<j`, connector `m-1<m`, path `i<i+1`), so each collected pair is
a unique non-self-loop edge; the loops read only their own vars (never `g`).
`extend_existing_index_edges_unrecorded` dedups on `canon_pair`, canonicalizes `edge_index_endpoints` by node
**name** (identical string comparison to `add_edge`), and pushes `adj_indices` in the given order, exactly as
the per-edge loop. All nodes are pre-added by `gen_nodes`. Verified: A/B parity `assert_eq!
(edges_ordered_borrowed + nodes_ordered)` on L(250,5) (255 nodes, ~31130 edges) passed before timing; suite
test `test_lollipop_graph` passes.

## Median A/B (paired-interleaved, one binary, NULL control)

`cargo test --release -p fnx-algorithms --lib lollipop_graph_batch_ab -- --ignored --nocapture`

L(250,5): 255 nodes, ~31130 edges (K₂₅₀ clique + 5-node stick). 61 rounds. Ratio = base/cand, **>1 = batch
faster**.

| row | median | win_rate | p5_p95 |
|-----|-------:|---------:|--------|
| `BATCH_vs_string` | **21.2793x** | 61/61 | [15.7382, 29.2944] |
| `NULL_batch_vs_batch` | 1.0018x | 32/61 | [0.8198, 1.1989] |

Decisive: candidate p5 (15.74) ~13x above the NULL p95 (1.20); all 61 rounds won.

## Clippy note

My change is clippy-clean (0 findings in production ~33806-33825 / test ~69504-69607, grep-verified). The
crate has 12 pre-existing clippy `-D warnings` errors in peer/committed code — left untouched per
shared-checkout discipline.

## Files

- Production: `crates/fnx-algorithms/src/lib.rs` — `lollipop_graph`.
- Test-only: `lollipop_graph_batch_ab` A/B.

## Vein status

Twenty-eighth result-builder batch win; 8th in the `gen_edge` index-batch gold seam (hypercube 11.55x,
multipartite 28.34x, bipartite 31.65x, turan 25.42x, windmill 17.90x, paley 26.47x, lollipop 21.28x). Clique-
dominated builders land in the same 20–30x band as the fully-dense ones. Next similar: `barbell_graph` (two
Kₘ cliques + path). Remaining reachable `gen_edge` generators are sparse (circulant few-offsets, ladders,
trees) or tiny fixed named-graphs.
