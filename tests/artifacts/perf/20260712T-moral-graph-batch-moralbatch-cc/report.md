# br-r37-c1-moralbatch — moral_graph (DAG moralization) batch-insert

Status: **SHIP.** 9.80x, byte-identical. Biggest fnx-algorithms result-builder batch win to date. My change
clippy-clean (crate has pre-existing peer lint debt, untouched).

## The target

`moral_graph(digraph)` (fnx-algorithms) builds the undirected moral graph of a DAG in two edge phases:

1. **directed → undirected:** every directed edge `(u,v)` added as an undirected edge.
2. **moralize (co-parents):** for each node, connect every pair of its predecessors.

Each edge in both phases was inserted via a per-edge `add_edge`.

## The lever

Collect all edges — phase-1 directed edges first, then phase-2 co-parent pairs, in the identical order —
and insert with one `Graph::extend_edges_unrecorded`.

## Why this is the biggest win (vs power 1.98x / cartesian 4.32x)

Phase 2 emits `Σ (indeg choose 2)` `add_edge` calls, and **most are duplicates**: different children share
parent pairs, so the same co-parent edge is re-added many times (and a co-parent edge may also duplicate a
phase-1 edge). On a simple `Graph` every such call is a dedup no-op — but still pays a per-edge **policy
record**. The batch pays that record **once**. So the batchable fraction here isn't `output ≈ |E|`, it's
`output << add_edge-call-count`: the dup-heavy builder is exactly where per-edge policy overhead piles up.

## Byte-identical argument

The loop reads only the **input** digraph (never `result`). `extend_edges_unrecorded` canonicalizes each
pair by node name and dedups on the canonical endpoint pair keeping the **first** occurrence — exactly as
`add_edge` on a simple Graph — and handles self-loops the same way. Collecting phase-1-then-phase-2 in the
same order preserves the same first-occurrences → identical adjacency. Predecessors of a node are distinct,
so co-parent pairs are never self-loops. Verified: A/B parity `assert_eq!(edges_ordered_borrowed +
nodes_ordered)` passed before timing (the `test result: ok` confirms the assert ran); the per-edge arm is a
verbatim replica of the production loop.

## Median A/B (paired-interleaved, one binary, NULL control)

`cargo test --release -p fnx-algorithms --lib moral_graph_batch_ab -- --ignored --nocapture`

Bipartite DAG: 60 parents (0..60) each point to 60 children (60..120). Phase 1 = 3600 directed edges;
phase 2 emits ~106k co-parent `add_edge` calls that dedup to 1770 unique. 61 rounds. Ratio = base/cand,
**>1 = batch faster**.

| row | median | win_rate | p5_p95 |
|-----|-------:|---------:|--------|
| `BATCH_vs_string` | **9.8030x** | 61/61 | [7.9960, 11.8068] |
| `NULL_batch_vs_batch` | 0.9878x | 28/61 | [0.8043, 1.1220] |

Decisive: candidate p5 (8.00) ~7x above the NULL p95 (1.12); all 61 rounds won.

## Clippy note

My change is clippy-clean (0 findings in production 40681-40705 / test 68060-68180, grep-verified). The
crate has 12 pre-existing clippy `-D warnings` errors in peer/committed code — left untouched per
shared-checkout discipline.

## Files

- Production: `crates/fnx-algorithms/src/lib.rs` — `moral_graph`.
- Test-only: `moral_graph_batch_ab` A/B.

## Vein status

Fifteenth fnx-algorithms result-builder batch win (plus the quotient_graph reject). Extends the "output ≈
|E|" rule: dup-heavy expanding builders (many `add_edge` calls collapsing to few unique edges) are the
*strongest* targets, because the per-edge policy record dominates. Next candidates: other dup-heavy /
expanding builders (`to_undirected`/`to_directed` conversions); skip collapsing builders (condensation,
contraction).
