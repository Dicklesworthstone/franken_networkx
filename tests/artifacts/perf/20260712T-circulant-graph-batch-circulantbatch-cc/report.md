# br-r37-c1-circulantbatch — circulant_graph INDEX-pair edge batch-insert

Status: **SHIP.** 19.19x, byte-identical (incl. the dedup path). My change clippy-clean (crate has
pre-existing peer lint debt, untouched).

## The target

`circulant_graph(n, offsets)` (fnx-algorithms) — the circulant graph Cₙ(offsets): `n` nodes (named
`"0".."n-1"` via `gen_nodes`), each node `i` connected to `(i+off)%n` for every offset (when `i≠j`), added
via the per-edge helper `gen_edge(&mut g, i, j)`. Density scales with `|offsets|`.

## The lever — INDEX batch (the `gen_edge` sub-lever)

Node index `i` *is* the loop variable. Collect the circulant edges as `(i, j)` **usize index pairs** and
insert with one `Graph::extend_existing_index_edges_unrecorded` — dropping both `to_string()` allocs, the
name→index hashes, and the per-edge policy record.

## Byte-identical argument (with dedup)

Unlike the earlier clique/partite generators, circulant **relies on dedup**: symmetric offsets (`off` and
`n-off`) revisit the same undirected edge. `add_edge` keeps the first and no-ops the rest;
`extend_existing_index_edges_unrecorded` dedups on `canon_pair` identically (`contains_key → continue`),
keeping the first occurrence, and — since both arms process `(i, off)` in the same order — the first
occurrence (hence the adjacency push order) is identical. It canonicalizes `edge_index_endpoints` by node
**name** exactly as `add_edge`; the `i≠j` guard reads only the loop vars. All nodes are pre-added by
`gen_nodes`. Verified: A/B parity `assert_eq!(edges_ordered_borrowed + nodes_ordered)` on circulant(1000,
`[1..50] + [950..999]`) — the symmetric offsets make every edge appear twice, so the 100000-pairs→50000-edges
dedup path is exercised on **every edge** and the assert confirms it. Suite test `test_circulant_graph`
passes.

## Median A/B (paired-interleaved, one binary, NULL control)

`cargo test --release -p fnx-algorithms --lib circulant_graph_batch_ab -- --ignored --nocapture`

circulant(1000, `[1..50] + [950..999]`): 1000 nodes, 50000 edges (100000 collected pairs, half dup). 61
rounds. Ratio = base/cand, **>1 = batch faster**.

| row | median | win_rate | p5_p95 |
|-----|-------:|---------:|--------|
| `BATCH_vs_string` | **19.1947x** | 61/61 | [9.8763, 36.2682] |
| `NULL_batch_vs_batch` | 1.0020x | 32/61 | [0.8771, 1.2908] |

Decisive: candidate p5 (9.88) ~7.6x above the NULL p95 (1.29); all 61 rounds won. (Wider p5/p95 spread than
the smaller generators — the 1000-node build + 50000-edge dedup is a heavier, noisier workload — but the
candidate p5 is far clear of the null.)

## Clippy note

My change is clippy-clean (0 findings in production ~34199-34218 / test ~69749-69847, grep-verified). The
crate has 12 pre-existing clippy `-D warnings` errors in peer/committed code — left untouched per
shared-checkout discipline.

## Files

- Production: `crates/fnx-algorithms/src/lib.rs` — `circulant_graph`.
- Test-only: `circulant_graph_batch_ab` A/B.

## Vein status

Thirtieth result-builder batch win; 10th in the `gen_edge` index-batch gold seam. First one that exercises
the **dedup** path (symmetric offsets) — confirms `extend_existing_index_edges_unrecorded`'s keep-first is
byte-identical to `add_edge`'s dedup. Remaining reachable `gen_edge` generators are sparse (`tadpole`,
`circular_ladder`, `ladder`, trees) or tiny fixed named-graphs — the productive dense vein is now mined out.
