# br-r37-c1-cartprodbatch — cartesian_product materialize-once + batch

Status: **SHIP.** 4.32x, byte-identical. My change is clippy-clean (crate has pre-existing peer lint debt,
untouched — see below).

## The target

`cartesian_product(g, h)` (fnx-algorithms) builds the product graph. Its two edge blocks each iterated
`h.edges_ordered()` / `g.edges_ordered()` **inside** the outer-node loop — rebuilding the full edge Vec
once per outer node (`O(|g|·|h_edges| + |h|·|g_edges|)` throwaway `Vec<EdgeSnapshot>` allocations) — and
inserted each product edge with a per-edge `add_edge` (a policy record each). This is the
`redundant_edge_materialization` lever from the ledger.

## The lever

Materialize `h.edges_ordered()` / `g.edges_ordered()` **once**, collect the product edge name-pairs in the
same order, and insert them with one `Graph::extend_edges_unrecorded` (one policy record for the batch).

## Byte-identical argument

The two edge blocks are the "same-G / adjacent-H" (horizontal) and "same-H / adjacent-G" (vertical)
families — provably disjoint (a horizontal edge's endpoints share their G-coordinate; a vertical edge's
share their H-coordinate; matching both forces `a == b` on a non-self-loop edge, a contradiction), and
`g`/`h` edges are non-self-loop → every product edge is unique with no self-loop. `extend_edges_unrecorded`
canonicalizes + pushes adjacency exactly as `add_edge` (it only skips the per-edge policy record), and the
pairs are collected in the identical block order. Verified: A/B parity
`assert_eq!(edges_ordered_borrowed + nodes_ordered)` on K60×K60; the 6 existing `test_cartesian_product_*`
suite tests (path×path, K2×K3, label-disambiguation, empties, directed) all pass against the batch.

## Median A/B (paired-interleaved, one binary, NULL control)

`cargo test --release -p fnx-algorithms --lib cartesian_product_batch_ab -- --ignored --nocapture`

K60 × K60 (3600 nodes, 212400 edges). 61 rounds. Ratio = base/cand, **>1 = batch faster**.

| row | median | win_rate | p5_p95 |
|-----|-------:|---------:|--------|
| `BATCH_vs_string` | **4.3177x** | 61/61 | [3.1950, 6.0091] |
| `NULL_batch_vs_batch` | 1.0223x | 35/61 | [0.8275, 1.2215] |

Decisive: candidate p5 (3.20) ~2.6x above the NULL p95 (1.22); all 61 rounds won.

## Clippy note

My change is clippy-clean. `clippy -p fnx-algorithms --lib --tests -- -D warnings` reports ~12 errors, but
**all** are in pre-existing peer/committed code surfaced by a newer clippy (`collapsible_if` let-chain
expansion at ~22069; `doc list item without indentation` in other agents' A/B-test doc comments —
`br-r37-c1-voronoi` ~49230, `br-r37-c1-branch` ~50813, etc.). None fall in this lever's ranges (production
39617-39646, test 66287-66405), verified by grep. Shared-checkout discipline forbids modifying peer code,
so they are left untouched; this lever adds no new findings.

## Files

- Production: `crates/fnx-algorithms/src/lib.rs` — `cartesian_product`.
- Test-only: `cartesian_product_batch_ab` A/B.

## Vein status

First non-generator lever this session (`redundant_edge_materialization` family). Opens the graph-product
operator family — the same materialize-once + batch applies to `cartesian_product_directed`,
`tensor_product`, `tensor_product_directed`, and the strong/lexicographic products (each iterates
`edges_ordered()` inside an outer-node loop).
