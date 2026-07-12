# br-r37-c1-gennodesbatch — gen_nodes bulk node-insert (shared helper)

Status: **SHIP.** 5.49x on the node-build, byte-identical. My change clippy-clean (crate has pre-existing peer
lint debt, untouched). **Speeds up the whole classic-generator family** (one shared-helper change).

## The target

`gen_nodes(g, n)` (fnx-algorithms, private helper) — adds nodes `"0".."n-1"` via a per-node `add_node`. It is
called by essentially every classic graph generator (`complete_bipartite_graph`, `complete_multipartite_
graph`, `turan_graph`, `hypercube_graph`, `paley_graph`, `lollipop_graph`, `barbell_graph`, `circulant_graph`,
`windmill_graph`, `wheel_graph`, `ladder_graph`, `balanced_tree`, the named-graphs, …). Each `add_node` pays a
`record_decision` policy-ledger entry + a redundant `contains_key` + a name clone.

## The lever

One bulk `Graph::extend_nodes_unrecorded((0..n).map(|i| i.to_string()))` instead of the per-node loop. After
the 30 shipped edge-batch levers, `gen_nodes` is the dominant remaining cost in each generator's build; this
is the shared complement.

## Byte-identical argument

The nodes `"0".."n-1"` are distinct and fresh, so `extend_nodes_unrecorded` inserts each with the same empty
`AttrMap` and the same `adj_indices.push(Vec::new())` as `add_node`, in the identical order — producing an
identical `nodes` IndexMap and adjacency, hence an identical index→name mapping for the subsequent edge loops.
The only difference is the internal `RuntimePolicy` ledger (n `"add_node"` records → one
`"extend_nodes_unrecorded"` record), which is not observable in `nodes_ordered`/`edges_ordered`/adjacency —
exactly the deliberate "unrecorded" tradeoff already shipped in all 30 edge batches. Verified: A/B parity
`assert_eq!(nodes_ordered + node_count)` on 100000 nodes passed before timing; **15 generator suite tests pass
unchanged** (complete_bipartite, complete_multipartite, turan, hypercube, paley, lollipop, barbell, circulant,
windmill, wheel, ladder, balanced_tree, petersen, kneser, grid_2d).

## Median A/B (paired-interleaved, one binary, NULL control)

`cargo test --release -p fnx-algorithms --lib gen_nodes_batch_ab -- --ignored --nocapture`

Node-build in isolation, 100000 nodes. 61 rounds. Ratio = base/cand, **>1 = batch faster**.

| row | median | win_rate | p5_p95 |
|-----|-------:|---------:|--------|
| `BATCH_vs_string` | **5.4874x** | 61/61 | [4.2614, 6.5388] |
| `NULL_batch_vs_batch` | 0.9944x | 29/61 | [0.8424, 1.2106] |

Decisive: candidate p5 (4.26) ~3.5x above the NULL p95 (1.21); all 61 rounds won.

## Clippy note

My change is clippy-clean (0 findings in production ~33064-33072 / test ~69854-69934, grep-verified). The
crate has 12 pre-existing clippy `-D warnings` errors in peer/committed code — left untouched per
shared-checkout discipline.

## Files

- Production: `crates/fnx-algorithms/src/lib.rs` — `gen_nodes`.
- Test-only: `gen_nodes_batch_ab` A/B.

## Vein status

Thirty-first result-builder batch win, and the first on the **node-build** side. Pairs with the `gen_edge`
index-batch seam: together they batch both phases (nodes + edges) of the classic-generator family. The
generator batch family is now essentially complete on both axes.
