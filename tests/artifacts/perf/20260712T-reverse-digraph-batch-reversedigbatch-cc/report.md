# br-r37-c1-reversedigbatch — reverse_digraph batch-insert (with attrs)

Status: **SHIP.** 2.40x, byte-identical. My change clippy-clean (crate has pre-existing peer lint debt,
untouched).

## The target

`reverse_digraph(g)` (fnx-algorithms) reverses every edge (`right → left`) carrying its attrs, inserting
each with a per-edge `add_edge_with_attrs` (a policy record each).

## The lever

Collect the reversed edges as `(right, left, attrs)` tuples and insert with one
`DiGraph::extend_edges_with_attrs_unrecorded`.

## Byte-identical argument

The reversed edges are a bijection of the input's distinct directed edges, so they are all unique (a
self-loop `(u,u)` reverses to itself, handled). `extend_edges_with_attrs_unrecorded` inserts the edge +
pushes `succ_indices`/`pred_indices` in insertion order and merges/keeps attrs exactly as
`add_edge_with_attrs`. Verified: A/B parity `assert_eq!(edges_ordered_borrowed + nodes_ordered)` on the
reverse of complete-digraph K60. Note: `reverse_digraph` has no dedicated exact-vs-nx suite test, so
byte-identity rests on the A/B parity, where `build_old` is a **verbatim replica** of the production
per-edge `add_edge_with_attrs` loop (same posture as `gnp_random_digraph`). The change preserves the exact
prior behavior and introduces no regression.

## Median A/B (paired-interleaved, one binary, NULL control)

`cargo test --release -p fnx-algorithms --lib reverse_digraph_batch_ab -- --ignored --nocapture`

reverse of complete-digraph K60 (60 nodes, 3540 directed edges). 61 rounds. Ratio = base/cand, **>1 =
batch faster**.

| row | median | win_rate | p5_p95 |
|-----|-------:|---------:|--------|
| `BATCH_vs_string` | **2.3976x** | 61/61 | [2.0685, 2.7113] |
| `NULL_batch_vs_batch` | 0.9959x | 26/61 | [0.8101, 1.1106] |

Decisive: candidate p5 (2.07) ~1.9x above the NULL p95 (1.11); all 61 rounds won. Smaller than the dense
result-builders because reverse is `|E|`-bounded (no O(n²)/dense structure) — the win is the per-edge
policy record folded to one bulk insert.

## Clippy note

My change is clippy-clean (0 findings in production 37669-37690 / test 67298-67418, grep-verified). The
crate has ~12 pre-existing clippy `-D warnings` errors in peer/committed code — left untouched per
shared-checkout discipline.

## Files

- Production: `crates/fnx-algorithms/src/lib.rs` — `reverse_digraph`.
- Test-only: `reverse_digraph_batch_ab` A/B.

## Vein status

Ninth fnx-algorithms result-builder batch (4 products, 2 complements, 2 line graphs, reverse). First to use
the *with-attrs* batch inserter (`extend_edges_with_attrs_unrecorded`) — opens attr-carrying result-builders.
Next: `power`, and sweep for more per-edge `add_edge(_with_attrs)` result-builders.
