# br-r37-c1-paleybatch — paley_graph INDEX-pair edge batch-insert

Status: **SHIP.** 26.47x, byte-identical. My change clippy-clean (crate has pre-existing peer lint debt,
untouched).

## The target

`paley_graph(q)` (fnx-algorithms) = the Paley graph of order q: `q` nodes (named `"0".."q-1"` via
`gen_nodes`), an edge between `i<j` whenever their difference is a quadratic residue mod q (`is_qr[(j-i) %
q]`), added via the per-edge helper `gen_edge(&mut g, i, j)`. For `q ≡ 1 (mod 4)` prime this is a dense
`(q-1)/2`-regular graph.

## The lever — INDEX batch (the `gen_edge` sub-lever)

Node index `i` *is* the loop variable. Collect the QR-difference edges as `(i, j)` **usize index pairs** and
insert with one `Graph::extend_existing_index_edges_unrecorded` — dropping both `to_string()` allocs, the
name→index hashes, and the per-edge policy record. Cheap `is_qr` lookup guard (like kneser) + dense-few-nodes.

## Byte-identical argument

`j` starts at `i+1`, so every collected `(i, j)` has `i < j` — a unique non-self-loop edge; the guard reads
only the precomputed `is_qr` table (never `g`). `extend_existing_index_edges_unrecorded` dedups on
`canon_pair`, canonicalizes `edge_index_endpoints` by node **name** (identical string comparison to
`add_edge`), and pushes `adj_indices` in the given order, exactly as the per-edge loop. All nodes are
pre-added by `gen_nodes`. Verified: A/B parity `assert_eq!(edges_ordered_borrowed + nodes_ordered)` on
Paley(193) (193 nodes, ~9264 edges) passed before timing; suite test `test_paley_graph_5` passes.

## Median A/B (paired-interleaved, one binary, NULL control)

`cargo test --release -p fnx-algorithms --lib paley_graph_batch_ab -- --ignored --nocapture`

Paley(193) (193 prime ≡ 1 mod 4): 193 nodes, ~9264 edges (avg degree 96). 61 rounds. Ratio = base/cand,
**>1 = batch faster**.

| row | median | win_rate | p5_p95 |
|-----|-------:|---------:|--------|
| `BATCH_vs_string` | **26.4733x** | 61/61 | [21.1462, 35.5866] |
| `NULL_batch_vs_batch` | 1.0139x | 37/61 | [0.8249, 1.2179] |

Decisive: candidate p5 (21.15) ~17x above the NULL p95 (1.22); all 61 rounds won.

## Clippy note

My change is clippy-clean (0 findings in production ~34273-34292 / test ~69393-69493, grep-verified). The
crate has 12 pre-existing clippy `-D warnings` errors in peer/committed code — left untouched per
shared-checkout discipline.

## Files

- Production: `crates/fnx-algorithms/src/lib.rs` — `paley_graph`.
- Test-only: `paley_graph_batch_ab` A/B.

## Vein status

Twenty-seventh result-builder batch win; 7th in the `gen_edge` index-batch gold seam (hypercube 11.55x,
multipartite 28.34x, bipartite 31.65x, turan 25.42x, windmill 17.90x, paley 26.47x). The dense-few-node
generators consistently land in the 25–32x band. Remaining reachable `gen_edge` generators are sparse
(`circulant_graph` w/ few offsets, `barbell_graph`, `lollipop_graph`, ladders, trees) or tiny fixed
named-graphs — smaller expected wins.
