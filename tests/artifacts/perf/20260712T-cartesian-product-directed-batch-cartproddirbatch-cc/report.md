# br-r37-c1-cartproddirbatch — cartesian_product_directed materialize-once + batch

Status: **SHIP.** 4.19x, byte-identical. My change clippy-clean (crate has pre-existing peer lint debt,
untouched).

## The target

`cartesian_product_directed(g, h)` (fnx-algorithms) — the DiGraph analog of `cartesian_product`, with the
same redundancy: `h.edges_ordered()` / `g.edges_ordered()` rebuilt once per outer node, plus per-edge
`add_edge`.

## The lever

Materialize the h/g edge lists once, collect the product edge name-pairs in the same order, and insert
with one `DiGraph::extend_edges_unrecorded`. (Mechanical clone of the shipped `cartesian_product` fix.)

## Byte-identical argument

Same as the undirected case: the two directed edge blocks (same-G/adjacent-H, same-H/adjacent-G) are
disjoint, and g/h edges are non-self-loop, so every product edge is a unique directed pair with no
self-loop. `extend_edges_unrecorded` pushes succ/pred adjacency exactly as `add_edge`, in the same order.
Verified: A/B parity `assert_eq!(edges_ordered_borrowed + nodes_ordered)` on complete-digraph K50×K50; the
existing `test_cartesian_product_directed_path` suite test passes against the batch.

## Median A/B (paired-interleaved, one binary, NULL control)

`cargo test --release -p fnx-algorithms --lib cartesian_product_directed_batch_ab -- --ignored --nocapture`

complete-digraph K50 × K50 (2500 nodes, 245000 directed edges). 61 rounds. Ratio = base/cand, **>1 = batch
faster**.

| row | median | win_rate | p5_p95 |
|-----|-------:|---------:|--------|
| `BATCH_vs_string` | **4.1922x** | 61/61 | [1.6279, 6.2085] |
| `NULL_batch_vs_batch` | 0.9968x | 30/61 | [0.7366, 1.4205] |

Decidable: candidate p5 (1.63) clears the NULL p95 (1.42); all 61 rounds won. Directed-graph construction
is noisier (wider spread), but the separation holds.

## Clippy note

My change is clippy-clean (0 findings in the production 39659-39685 / test 66405-66523 ranges,
grep-verified). The crate carries ~12 pre-existing clippy `-D warnings` errors in peer/committed code
(collapsible_if let-chain; doc-list-indentation in other agents' A/B-test doc comments), surfaced by a
newer clippy — left untouched per shared-checkout discipline.

## Files

- Production: `crates/fnx-algorithms/src/lib.rs` — `cartesian_product_directed`.
- Test-only: `cartesian_product_directed_batch_ab` A/B.

## Vein status

Second product-operator lever (cartesian_product 4.32x + cartesian_product_directed 4.19x). Remaining in
family: `tensor_product` (~39682), `tensor_product_directed` (~39733), + strong/lexicographic products.
