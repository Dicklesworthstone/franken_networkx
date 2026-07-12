# br-r37-c1-powerbatch — power (k-th graph power) batch-insert

Status: **SHIP.** 1.98x, byte-identical. My change clippy-clean (crate has pre-existing peer lint debt,
untouched).

## The target

`power(graph, k)` builds the k-th graph power: a BFS from each source `s` up to distance `k`, adding an
edge `(s, ni)` (with `ni > s`) whenever a node `ni` is first reached. Each such edge was inserted via a
per-edge `add_edge`.

## The lever

Collect the power edges `(s, ni)` discovered during each source's BFS (same order) and insert with one
`Graph::extend_edges_unrecorded`.

## Byte-identical argument

The BFS reads only the **input** graph (never `result`); `ni > s` emits each power edge exactly once from
its smaller endpoint, and `ni != s`, so every collected pair is unique with no self-loop.
`extend_edges_unrecorded` canonicalizes + pushes adjacency exactly as `add_edge` (and dedups, though there
are no duplicates), in the identical BFS-discovery order. Verified: A/B parity
`assert_eq!(edges_ordered_borrowed + nodes_ordered)` on `power(K120, k=1)` (= K120, 7140 edges); the
existing `test_power_path` suite test passes against the batch. Marker `POWER_BATCH_AB` + test name
confirmed (fresh binary).

## Why this clears the null (vs the quotient reject)

`power`'s output edge count is `≈ |E|` (for a dense power graph, much larger), so the per-edge policy-drop
is a meaningful fraction of the total. This is the opposite of `quotient_graph` (rejected below-null),
whose output collapses to `O(blocks²)` while the input scan dominates.

## Median A/B (paired-interleaved, one binary, NULL control)

`cargo test --release -p fnx-algorithms --lib power_batch_ab -- --ignored --nocapture`

power(K120, k=1) (120 nodes, 7140 edges). 61 rounds. Ratio = base/cand, **>1 = batch faster**.

| row | median | win_rate | p5_p95 |
|-----|-------:|---------:|--------|
| `BATCH_vs_string` | **1.9768x** | 61/61 | [1.7631, 2.2286] |
| `NULL_batch_vs_batch` | 0.9987x | 30/61 | [0.9286, 1.1304] |

Decisive: candidate p5 (1.76) ~1.6x above the NULL p95 (1.13); all 61 rounds won.

## Clippy note

My change is clippy-clean (0 findings in production 38118-38160 / test 67922-68056, grep-verified). The
crate has ~12 pre-existing clippy `-D warnings` errors in peer/committed code — left untouched per
shared-checkout discipline.

## Files

- Production: `crates/fnx-algorithms/src/lib.rs` — `power`.
- Test-only: `power_batch_ab` A/B.

## Vein status

Fourteenth fnx-algorithms result-builder batch win (plus the quotient_graph reject). Confirms the "output
≈ |E|" rule from the quotient reject: power expands (dense output) → clears null; quotient collapses →
below null.
