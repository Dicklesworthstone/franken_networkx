# br-r37-c1-gridbatch — grid_graph edge batch-insert

Status: **SHIP.** 2.73x, byte-identical. My change clippy-clean (crate has pre-existing peer lint debt,
untouched).

## The target

`grid_graph(dim)` (fnx-algorithms) — the n-dimensional grid graph: nodes are coordinate tuples, and each
node connects to its `+1` neighbor in each dimension via a per-edge `add_edge`.

## The lever

Collect the grid edges (same i-major, dimension order) into one `Vec<(String, String)>` and insert with one
`Graph::extend_edges_unrecorded`. The `coords_to_label` String work is left in place (identical in both
arms) so the measurement isolates the policy-drop.

## Byte-identical argument

The edge loop reads only the **input** coords/dim (never `g`); each edge is emitted once from its lower
endpoint (`coords[d]+1 < dim[d]`), so every collected pair is a unique non-self-loop grid edge.
`extend_edges_unrecorded` resolves indices, dedups on `(s_idx, t_idx)`, and pushes adjacency exactly as
`add_edge`, in the identical order; all nodes are pre-added so every endpoint resolves. Verified: A/B parity
`assert_eq!(edges_ordered_borrowed + nodes_ordered)` on a 100×100 grid (10000 nodes, 19800 edges) passed
before timing, where the per-edge base arm is a **verbatim replica** of the pre-change production loop.
`grid_graph` has no dedicated Rust unit test, so byte-identity rests on this A/B parity plus the Python
differential tests (`tests/python/test_lattice_generators.py`, `test_classic_generators.py`) that exercise it
against the built `.so` — the same standard as prior no-Rust-suite ships (`ego_graph_directed`, `power`).

## Why the win is ~2.7x (not 12x like kneser)

Each edge's common work here is **two `coords_to_label` String allocations** (kept identical in both arms),
which is heavier than kneser's O(k) disjoint check. So the per-edge policy-drop is a smaller (but still
dominant) fraction — the `to_undirected`/`compose` tier rather than the cheap-guard kneser tier.

## Median A/B (paired-interleaved, one binary, NULL control)

`cargo test --release -p fnx-algorithms --lib grid_graph_batch_ab -- --ignored --nocapture`

100×100 grid: 10000 nodes, 19800 edges. 61 rounds. Ratio = base/cand, **>1 = batch faster**.

| row | median | win_rate | p5_p95 |
|-----|-------:|---------:|--------|
| `BATCH_vs_string` | **2.7268x** | 61/61 | [1.9440, 3.5373] |
| `NULL_batch_vs_batch` | 1.0143x | 35/61 | [0.8334, 1.1868] |

Decisive: candidate p5 (1.94) ~1.6x above the NULL p95 (1.19); all 61 rounds won.

## Clippy note

My change is clippy-clean (0 findings in production ~34016-34036 / test ~68707-68832, grep-verified). The
crate has 12 pre-existing clippy `-D warnings` errors in peer/committed code — left untouched per
shared-checkout discipline.

## Files

- Production: `crates/fnx-algorithms/src/lib.rs` — `grid_graph`.
- Test-only: `grid_graph_batch_ab` A/B.

## Vein status

Twenty-first result-builder batch win. Reachable via `grid_graph` pyo3 binding. The String-label cost caps
this at the ~2.7x tier (a follow-up could hoist the redundant per-dimension `coords_to_label(&coords)` source
recompute, but that's a separate lever). Next: other reachable per-edge generators (`chordal_cycle_graph`,
`hypercube_graph`, `dorogovtsev_goltsev_mendes_graph` if non-mutating).
