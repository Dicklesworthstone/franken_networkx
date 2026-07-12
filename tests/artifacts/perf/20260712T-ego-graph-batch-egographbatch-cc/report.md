# br-r37-c1-egographbatch — ego_graph induced-edge batch-insert

Status: **SHIP.** 1.77x, byte-identical. My change clippy-clean (crate has pre-existing peer lint debt,
untouched).

## The target

`ego_graph(graph, center, radius)` (fnx-algorithms) BFS-computes the nodes within `radius` of `center`,
then adds every input edge whose endpoints are both in the ego set via a per-edge `add_edge_with_attrs`.

## The lever

Collect the induced edges as `(left, right, attrs)` tuples and insert with one
`Graph::extend_edges_with_attrs_unrecorded`.

## Byte-identical argument

The loop never reads `result`; the input edges are distinct and non-self-loop, so every collected induced
edge is unique with no self-loop. `extend_edges_with_attrs_unrecorded` canonicalizes + pushes adjacency
exactly as `add_edge_with_attrs` (and dedups+merges, though there are no duplicates), in the identical
order. Verified: A/B parity `assert_eq!(edges_ordered_borrowed + nodes_ordered)` on the ego of K60 (= the
whole graph, 1770 edges); the 2 existing `test_ego_graph_*` suite tests (radius, full-radius) pass against
the batch. Marker `EGOGRAPH_BATCH_AB` + test name confirmed present (fresh binary).

## Median A/B (paired-interleaved, one binary, NULL control)

`cargo test --release -p fnx-algorithms --lib ego_graph_batch_ab -- --ignored --nocapture`

ego of K60 (60 nodes, 1770 induced edges). 61 rounds. Ratio = base/cand, **>1 = batch faster**.

| row | median | win_rate | p5_p95 |
|-----|-------:|---------:|--------|
| `BATCH_vs_string` | **1.7740x** | 61/61 | [1.5516, 1.9859] |
| `NULL_batch_vs_batch` | 1.0309x | 45/61 | [0.8794, 1.2021] |

Decisive: candidate p5 (1.55) above the NULL p95 (1.20); all 61 rounds won. Smaller than the dense
result-builders — ego's edge insertion is `|E|`-bounded and the BFS is common to both arms — so the win is
the per-edge policy record folded to one bulk insert.

## Clippy note

My change is clippy-clean (0 findings in production 38348-38370 / test 67670-67796, grep-verified). The
crate has ~12 pre-existing clippy `-D warnings` errors in peer/committed code — left untouched per
shared-checkout discipline.

## Files

- Production: `crates/fnx-algorithms/src/lib.rs` — `ego_graph`.
- Test-only: `ego_graph_batch_ab` A/B.

## Vein status

Twelfth fnx-algorithms result-builder batch. Next: `ego_graph_directed` (near-clone), `quotient_graph`,
`identified_nodes` (needs a skip-dup seen-set — reads result.has_edge), `power`.
