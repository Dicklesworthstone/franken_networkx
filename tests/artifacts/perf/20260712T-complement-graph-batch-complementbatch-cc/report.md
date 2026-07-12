# br-r37-c1-complementbatch — complement_graph batch-insert

Status: **SHIP.** 6.15x, byte-identical. My change clippy-clean (crate has pre-existing peer lint debt,
untouched).

## The target

`complement_graph(g)` (fnx-algorithms) iterates all `i < j` node pairs, checks `graph.has_edge(nodes[i],
nodes[j])` on the **input** graph, and adds each non-edge to the result via a per-edge `add_edge`. For a
sparse input the complement is dense (≈n²/2 edges), so there are many per-edge policy records.

## The lever

Collect the non-edge pairs and insert with one `Graph::extend_edges_unrecorded`.

## Byte-identical argument

`has_edge` reads the **input** graph (never the mutating result), so the collected pairs are exactly the
i<j non-edges — unique with no self-loop (`i != j`). `extend_edges_unrecorded` canonicalizes + pushes
adjacency exactly as `add_edge` (and dedups, though there are no duplicates here), in the identical order.
Verified: A/B parity `assert_eq!(edges_ordered_borrowed + nodes_ordered)` on the complement of a 500-node
cycle; the 9 existing `complement*` suite tests (path, triangle, involution, complete-is-empty, empties,
directed) all pass against the batch.

## Median A/B (paired-interleaved, one binary, NULL control)

`cargo test --release -p fnx-algorithms --lib complement_graph_batch_ab -- --ignored --nocapture`

complement of a 500-node cycle (500 nodes, ~124250 edges). 61 rounds. Ratio = base/cand, **>1 = batch
faster**.

| row | median | win_rate | p5_p95 |
|-----|-------:|---------:|--------|
| `BATCH_vs_string` | **6.1533x** | 61/61 | [4.7303, 8.5782] |
| `NULL_batch_vs_batch` | 1.0056x | 34/61 | [0.7740, 1.1353] |

Decisive: candidate p5 (4.73) ~4.2x above the NULL p95 (1.14); all 61 rounds won. Bigger than the product
operators because a sparse input yields a dense complement, so many per-edge policy records are dropped.

## Clippy note

My change is clippy-clean (0 findings in production 37620-37642 / test 66815-66940, grep-verified). The
crate has ~12 pre-existing clippy `-D warnings` errors in peer/committed code — left untouched per
shared-checkout discipline.

## Files

- Production: `crates/fnx-algorithms/src/lib.rs` — `complement_graph`.
- Test-only: `complement_graph_batch_ab` A/B.

## Vein status

`redundant_edge_materialization` / result-builder batch family (fnx-algorithms), fifth lever after the four
graph products. Next near-clone: `complement_digraph` (~37632, same non-edge loop for DiGraph).
