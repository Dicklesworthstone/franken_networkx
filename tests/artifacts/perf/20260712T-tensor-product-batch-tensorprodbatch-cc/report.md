# br-r37-c1-tensorprodbatch — tensor_product batch-insert

Status: **SHIP.** 3.78x, byte-identical. My change clippy-clean (crate has pre-existing peer lint debt,
untouched).

## The target

`tensor_product(g, h)` (fnx-algorithms). Its edge Vecs are **already** materialized once, but the double
loop over `g_edges × h_edges` still inserted each product edge (main + optional cross) with a per-edge
`add_edge` (a policy record each).

## The lever

Collect the product edges (same emission order) and insert with one `Graph::extend_edges_unrecorded`.

## Byte-identical argument

`extend_edges_unrecorded` **dedups** on the canonical endpoint pair (`self.edges.contains_key(&edge_key)
→ continue`, fnx-classes/src/lib.rs:1300), keeping first occurrence — exactly like `add_edge`. So the
`add_cross` self-loop-induced duplicates (a G self-loop makes the cross edge equal the main edge) are
skipped identically. Endpoint canonicalization + adjacency-row order + edge-storage order all match
`add_edge`, and the pairs are collected in the identical order. Verified: A/B parity
`assert_eq!(edges_ordered_borrowed + nodes_ordered)` on K30×K30; the 5 existing `test_tensor_product_*`
suite tests (path×path, triangle_edge, directed, empties) all pass against the batch.

## Median A/B (paired-interleaved, one binary, NULL control)

`cargo test --release -p fnx-algorithms --lib tensor_product_batch_ab -- --ignored --nocapture`

K30 × K30 (900 nodes; 435×435 g/h edge-pairs). 61 rounds. Ratio = base/cand, **>1 = batch faster**.

| row | median | win_rate | p5_p95 |
|-----|-------:|---------:|--------|
| `BATCH_vs_string` | **3.7841x** | 61/61 | [2.8352, 5.3608] |
| `NULL_batch_vs_batch` | 1.0164x | 36/61 | [0.8481, 1.2608] |

Decisive: candidate p5 (2.84) ~2.3x above the NULL p95 (1.26); all 61 rounds won. (A profile-first run
before the edit gave 3.90x.) Since the edge Vecs were already materialized, the win is the per-edge policy
record folded to one bulk record.

## Clippy note

My change is clippy-clean (0 findings in production 39717-39750 / test 66523-66691, grep-verified). The
crate has ~12 pre-existing clippy `-D warnings` errors in peer/committed code (collapsible_if;
doc-list-indentation in other agents' A/B-test doc comments) — left untouched per shared-checkout discipline.

## Files

- Production: `crates/fnx-algorithms/src/lib.rs` — `tensor_product`.
- Test-only: `tensor_product_batch_ab` A/B.

## Vein status

Third product-operator lever (cartesian_product 4.32x + cartesian_product_directed 4.19x + tensor_product
3.78x). Remaining: `tensor_product_directed` (~39750), + strong/lexicographic products.
