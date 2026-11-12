# br-r37-c1-linegraphdirbatch — line_graph_directed batch-insert

Status: **SHIP.** 5.24x, byte-identical. My change clippy-clean (crate has pre-existing peer lint debt,
untouched).

## The target

`line_graph_directed(g)` (fnx-algorithms) builds the directed L(G): a node per edge, and a directed L(G)
edge `(u,v) → (u2,v2)` for each pair of input edges with `v == u2`. `from_node` is already hoisted, but
each matching L(G) edge is inserted with a per-edge `add_edge`.

## The lever

Collect the directed L(G) edges (same emission order) and insert with one
`DiGraph::extend_edges_unrecorded`.

## Byte-identical argument

Each `(outer, inner)` match yields a directed L(G) edge uniquely determined by that pair; the input edges
are distinct, so every L(G) edge is unique (self-loops only from an input self-loop `(u,u)`, handled).
`extend_edges_unrecorded` pushes succ/pred adjacency exactly as `add_edge` (and dedups on the directed
key, though there are no duplicates), in the identical order. Verified: A/B parity
`assert_eq!(edges_ordered_borrowed + nodes_ordered)` on L(complete-digraph K30); the 4 existing
`line_graph_directed*` suite tests (converging, diverging, path, empty) all pass against the batch.

## Median A/B (paired-interleaved, one binary, NULL control)

`cargo test --release -p fnx-algorithms --lib line_graph_directed_batch_ab -- --ignored --nocapture`

L(complete-digraph K30) (870 nodes). 61 rounds. Ratio = base/cand, **>1 = batch faster**.

| row | median | win_rate | p5_p95 |
|-----|-------:|---------:|--------|
| `BATCH_vs_string` | **5.2421x** | 61/61 | [4.1866, 6.3978] |
| `NULL_batch_vs_batch` | 0.9995x | 30/61 | [0.8185, 1.2324] |

Decisive: candidate p5 (4.19) ~3.4x above the NULL p95 (1.23); all 61 rounds won.

## Clippy note

My change is clippy-clean (0 findings in production 39590-39620 / test 67175-67297, grep-verified). The
crate has ~12 pre-existing clippy `-D warnings` errors in peer/committed code — left untouched per
shared-checkout discipline.

## Files

- Production: `crates/fnx-algorithms/src/lib.rs` — `line_graph_directed`.
- Test-only: `line_graph_directed_batch_ab` A/B.

## Vein status

Eighth fnx-algorithms result-builder batch (4 products, 2 complements, 2 line graphs). Next: `power`,
`reverse_digraph`.
