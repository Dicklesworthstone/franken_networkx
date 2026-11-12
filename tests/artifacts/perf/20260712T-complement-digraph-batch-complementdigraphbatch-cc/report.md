# br-r37-c1-complementdigraphbatch — complement_digraph batch-insert

Status: **SHIP.** 5.39x, byte-identical. My change clippy-clean (crate has pre-existing peer lint debt,
untouched).

## The target

`complement_digraph(g)` (fnx-algorithms) — the DiGraph analog of `complement_graph`: it iterates all
ordered pairs `u != v`, checks `has_edge(u, v)` on the **input**, and adds each non-edge to the result via
per-edge `add_edge`. For a sparse input the directed complement is dense.

## The lever

Collect the directed non-edge pairs and insert with one `DiGraph::extend_edges_unrecorded`.

## Byte-identical argument

`has_edge` reads the **input** digraph (never the mutating result), so the collected pairs are exactly the
`u != v` non-edges — each a unique directed edge with no self-loop. `extend_edges_unrecorded` pushes
succ/pred adjacency exactly as `add_edge` (and dedups on the directed key, though there are no duplicates),
in the identical order. Verified: A/B parity `assert_eq!(edges_ordered_borrowed + nodes_ordered)` on the
directed complement of a 400-node directed cycle; the existing `complement_directed_test` suite test passes.

## Median A/B (paired-interleaved, one binary, NULL control)

`cargo test --release -p fnx-algorithms --lib complement_digraph_batch_ab -- --ignored --nocapture`

directed complement of a 400-node directed cycle (400 nodes, ~158800 directed edges). 61 rounds. Ratio =
base/cand, **>1 = batch faster**.

| row | median | win_rate | p5_p95 |
|-----|-------:|---------:|--------|
| `BATCH_vs_string` | **5.3869x** | 61/61 | [3.6592, 8.1178] |
| `NULL_batch_vs_batch` | 0.9869x | 27/61 | [0.8715, 1.1763] |

Decisive: candidate p5 (3.66) ~3.1x above the NULL p95 (1.18); all 61 rounds won.

## Clippy note

My change is clippy-clean (0 findings in production 37640-37665 / test 66933-67043, grep-verified). The
crate has ~12 pre-existing clippy `-D warnings` errors in peer/committed code — left untouched per
shared-checkout discipline.

## Files

- Production: `crates/fnx-algorithms/src/lib.rs` — `complement_digraph`.
- Test-only: `complement_digraph_batch_ab` A/B.

## Vein status

Sixth fnx-algorithms result-builder batch (4 products + complement_graph + complement_digraph). Next
per-edge result-builders to sweep: `line_graph`, `line_graph_directed`, `power`, `reverse_digraph`
(add_edge_with_attrs per edge).
