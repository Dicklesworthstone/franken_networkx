# br-r37-c1-composebatch — graph_compose edge batch-insert

Status: **SHIP.** 2.74x, byte-identical. My change clippy-clean (crate has pre-existing peer lint debt,
untouched).

## The target

`graph_compose(g1, g2)` (fnx-algorithms) = `networkx.compose`: start from all of g2 (nodes + edges), then
layer g1 on top so g1's attrs overwrite g2's on shared edges. Both the g2 and g1 edge loops call
`add_edge_with_attrs` **unconditionally** (g1's later call overwrites via the attr merge).

## The lever

Collect g2 edges then g1 edges (identical order) into one `Vec<(String, String, AttrMap)>` and insert with
one `Graph::extend_edges_with_attrs_unrecorded`. The g1 *node* loop stays in place between the two edge
collections.

## Byte-identical argument

Neither edge loop reads `result` (both are unconditional), so nothing depends on intermediate result state.
`extend_edges_with_attrs_unrecorded` dedups on the canonical endpoint pair and merges attrs via the same
`existing.extend(attrs)` as `add_edge_with_attrs` — so for a shared edge, g2 (pushed first) is inserted, then
g1 (pushed second) overwrites its conflicting keys: **the identical g2-then-g1 sequence** as production. All
nodes are pre-added (g2 node loop + the retained g1 node loop), so every endpoint resolves to an existing
index; the g2/g1 edge relative order is preserved. Verified: A/B parity `assert_eq!(edges_ordered_borrowed +
nodes_ordered)` on two overlapping complete K200 graphs — every g1 edge merge-dups a g2 edge, so the
`19900`-output-from-`39800`-calls dedup/merge branch is exercised on **every edge** and the assert confirms
the collapse + ordering. Suite test `test_graph_compose` passes. The attr-value overwrite is guaranteed by
the documented `extend`-equivalence (extend_edges_with_attrs_unrecorded's dup branch is a verbatim
`existing.extend(attrs)`, matching add_edge_with_attrs).

## Why this clears the null

The overlapping compose is dup-heavy: `|E1| + |E2|` = 39800 `add_edge_with_attrs` calls (half merge-dups)
each paid a policy record; the batch pays one. Same shape as `to_undirected` (reciprocal merge) and
`moral_graph` (co-parent dups), a ~2.7× tier.

## Median A/B (paired-interleaved, one binary, NULL control)

`cargo test --release -p fnx-algorithms --lib graph_compose_batch_ab -- --ignored --nocapture`

Two overlapping complete K200 graphs (same node set); compose = 19900 edges from 39800 add_edge calls.
61 rounds. Ratio = base/cand, **>1 = batch faster**.

| row | median | win_rate | p5_p95 |
|-----|-------:|---------:|--------|
| `BATCH_vs_string` | **2.7416x** | 61/61 | [1.8926, 3.6844] |
| `NULL_batch_vs_batch` | 1.0144x | 31/61 | [0.8447, 1.2209] |

Decisive: candidate p5 (1.89) ~1.5x above the NULL p95 (1.22); all 61 rounds won.

## Clippy note

My change is clippy-clean (0 findings in production ~24537-24557 / test ~68459-68583, grep-verified). The
crate has 12 pre-existing clippy `-D warnings` errors in peer/committed code — left untouched per
shared-checkout discipline.

## Files

- Production: `crates/fnx-algorithms/src/lib.rs` — `graph_compose`.
- Test-only: `graph_compose_batch_ab` A/B.

## Vein status

Nineteenth result-builder batch win. Reachable via `graph_compose` pyo3 binding. Note: `graph_union` (reads
`result.has_edge` mid-loop → g1-wins skip, incompatible with the merging inserter) and `graph_intersection`
(collapsing filter) were examined and **rejected** as non-levers. Next: `dedensify` (reachable, structural),
or other expanding builders.
