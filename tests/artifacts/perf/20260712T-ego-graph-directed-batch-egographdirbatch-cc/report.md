# br-r37-c1-egographdirbatch — ego_graph_directed induced-edge batch-insert

Status: **SHIP.** 2.16x, byte-identical. My change clippy-clean (crate has pre-existing peer lint debt,
untouched).

## The target

`ego_graph_directed(g, center, radius)` (fnx-algorithms) — the DiGraph analog of `ego_graph`: BFS-computes
the ego set, then adds every input edge whose endpoints are both in the set via a per-edge
`add_edge_with_attrs`.

## The lever

Collect the induced directed edges as `(left, right, attrs)` tuples and insert with one
`DiGraph::extend_edges_with_attrs_unrecorded`.

## Byte-identical argument

The loop never reads `result`; the input edges are distinct, so every collected induced edge is a unique
directed pair with no self-loop. `extend_edges_with_attrs_unrecorded` pushes succ/pred adjacency exactly
as `add_edge_with_attrs`, in the identical order. Verified: A/B parity `assert_eq!(edges_ordered_borrowed
+ nodes_ordered)` on the ego of complete-digraph K50 (= the whole graph, 2450 directed edges). `ego_graph_directed`
has no dedicated exact-vs-nx suite test, so byte-identity rests on the A/B parity, where the per-edge arm
is a **verbatim replica** of the production loop (same posture as `gnp_random_digraph`). The change
preserves the exact prior behavior; no regression.

The initial A/B run hit a **stale rch test binary** (0 tests matched); the retry loop caught the missing
`EGOGRAPHDIR_BATCH_AB` marker and re-ran to a fresh binary that showed the marker + test name.

## Median A/B (paired-interleaved, one binary, NULL control)

`cargo test --release -p fnx-algorithms --lib ego_graph_directed_batch_ab -- --ignored --nocapture`

ego of complete-digraph K50 (50 nodes, 2450 directed induced edges). 61 rounds. Ratio = base/cand, **>1 =
batch faster**.

| row | median | win_rate | p5_p95 |
|-----|-------:|---------:|--------|
| `BATCH_vs_string` | **2.1646x** | 60/61 | [1.8173, 3.0582] |
| `NULL_batch_vs_batch` | 1.0023x | 31/61 | [0.8538, 1.1362] |

Decisive: candidate p5 (1.82) ~1.6x above the NULL p95 (1.14); 60/61 rounds won (one round noise-slower).

## Clippy note

My change is clippy-clean (0 findings in production 38417-38435 / test 67795-67920, grep-verified). The
crate has ~12 pre-existing clippy `-D warnings` errors in peer/committed code — left untouched per
shared-checkout discipline.

## Files

- Production: `crates/fnx-algorithms/src/lib.rs` — `ego_graph_directed`.
- Test-only: `ego_graph_directed_batch_ab` A/B.

## Vein status

Thirteenth fnx-algorithms result-builder batch. Next: `quotient_graph`, `power`, `identified_nodes`
(skip-dup seen-set).
