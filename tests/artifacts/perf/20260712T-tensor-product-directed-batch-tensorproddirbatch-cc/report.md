# br-r37-c1-tensorproddirbatch — tensor_product_directed batch-insert

Status: **SHIP.** 4.54x, byte-identical. My change clippy-clean (crate has pre-existing peer lint debt,
untouched).

## The target

`tensor_product_directed(g, h)` (fnx-algorithms). Edge Vecs already materialized; the `g_edges × h_edges`
double loop inserted each directed product edge `(gu,hu) → (gv,hv)` with a per-edge `add_edge`.

## The lever

Collect the directed product edges (same emission order) and insert with one
`DiGraph::extend_edges_unrecorded`.

## Byte-identical argument

Each `(g-edge, h-edge)` pair yields exactly one directed product edge, uniquely determined by that edge →
no duplicates; `extend_edges_unrecorded` dedups on the directed key anyway and handles self-loops
(`left == right`) identically to `add_edge`. Verified: A/B parity `assert_eq!(edges_ordered_borrowed +
nodes_ordered)` on complete-digraph K25×K25; the existing `test_tensor_product_directed` suite test passes.

## Median A/B (paired-interleaved, one binary, NULL control)

`cargo test --release -p fnx-algorithms --lib tensor_product_directed_batch_ab -- --ignored --nocapture`

complete-digraph K25 × K25 (625 nodes, 360000 directed product edges). 61 rounds. Ratio = base/cand, **>1
= batch faster**.

| row | median | win_rate | p5_p95 |
|-----|-------:|---------:|--------|
| `BATCH_vs_string` | **4.5399x** | 61/61 | [3.6748, 5.5426] |
| `NULL_batch_vs_batch` | 1.0012x | 31/61 | [0.8032, 1.2375] |

Decisive: candidate p5 (3.67) ~3.0x above the NULL p95 (1.24); all 61 rounds won.

## Clippy note

My change is clippy-clean (0 findings in production 39772-39790 / test 66690-66818, grep-verified). The
crate has ~12 pre-existing clippy `-D warnings` errors in peer/committed code — left untouched per
shared-checkout discipline.

## Files

- Production: `crates/fnx-algorithms/src/lib.rs` — `tensor_product_directed`.
- Test-only: `tensor_product_directed_batch_ab` A/B.

## Vein status

Fourth product-operator lever (cartesian 4.32x, cartesian_directed 4.19x, tensor 3.78x, tensor_directed
4.54x). The four core graph products are now batched. Remaining in family: strong / lexicographic products
(if present).
