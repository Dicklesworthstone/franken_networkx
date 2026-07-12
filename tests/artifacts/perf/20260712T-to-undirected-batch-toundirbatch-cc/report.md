# br-r37-c1-toundirbatch — DiGraph::to_undirected reciprocal-edge batch-insert

Status: **SHIP.** 2.01x, byte-identical. My change clippy-clean (fnx-classes crate has zero lint debt).

## The target

`DiGraph::to_undirected(&self) -> Graph` (fnx-classes core) adds every node, then walks
`self.edges_ordered()` inserting each directed edge into the undirected result via a per-edge
`add_edge_with_attrs`. Reciprocal directed edges `a→b` and `b→a` both canonicalize to the undirected `{a,b}`
→ the later-processed direction merges its attrs into the first (later wins).

## The lever

Collect the directed edges as `(left, right, attrs)` (identical `edges_ordered()` order) and insert with one
`Graph::extend_edges_with_attrs_unrecorded`.

## Why this is dup-heavy (the moral_graph family)

On a reciprocal-heavy digraph roughly **half** the `add_edge_with_attrs` calls are merge-dups (both
directions of every mutual edge), and every one paid a per-edge **policy record**. The batch pays that
record once. This is the same shape as `moral_graph` (br-r37-c1-moralbatch) — per-edge policy overhead on
dedup/merge no-ops — just a milder ~2× dup ratio.

## Byte-identical argument

`extend_edges_with_attrs_unrecorded` dedups on the canonical endpoint pair and merges attrs via the same
`existing.extend(attrs)` (later direction wins) as `add_edge_with_attrs`, in the identical order. All nodes
are pre-added first, so every edge endpoint resolves to an existing index — the batch never creates a node
or clobbers node attrs. Verified three ways: (1) A/B parity `assert_eq!(edges_ordered_borrowed +
nodes_ordered)` on complete-digraph K200 (39800 directed → 19900 undirected) passed before timing; (2) the
dedicated suite test `to_undirected_merges_edges` (reciprocal attr-merge) passes; (3)
`to_undirected_preserves_runtime_policy` passes.

## Median A/B (paired-interleaved, one binary, NULL control)

`cargo test --release -p fnx-classes --lib to_undirected_batch_ab -- --ignored --nocapture`

Complete digraph K200 (every ordered pair `a→b`, 39800 directed edges → 19900 undirected). 61 rounds.
Ratio = base/cand, **>1 = batch faster**.

| row | median | win_rate | p5_p95 |
|-----|-------:|---------:|--------|
| `BATCH_vs_string` | **2.0083x** | 61/61 | [1.8222, 2.2859] |
| `NULL_batch_vs_batch` | 1.0000x | 31/61 | [0.8605, 1.1344] |

Decisive: candidate p5 (1.82) ~1.6x above the NULL p95 (1.13); all 61 rounds won.

### Sizing note (measurement methodology)

A first pass at K100 (9900 directed edges) measured the same median (2.02x, 59/61) but the sub-millisecond
workload left the null tail wide (p95 1.55), so candidate p5 (1.26) did not clear null p95 — a timer-noise
floor, not a weak lever. Bumping to K200 amortized the fixed per-round overhead, tightened the null to
[0.86, 1.13], and lifted candidate p5 to 1.82 → decisive. The effect was real at both sizes; only the tails
needed the larger workload to separate.

## Clippy note

fnx-classes is clippy-clean crate-wide (0 findings), and none of my lines (production ~1797-1811 / test
~3784-3884) are flagged.

## Files

- Production: `crates/fnx-classes/src/digraph.rs` — `DiGraph::to_undirected`.
- Test-only: `to_undirected_batch_ab` A/B.

## Vein status

Sixteenth result-builder batch win — and the first in the **core fnx-classes crate** (the prior 15 were in
fnx-algorithms). Extends the dup-heavy moral_graph refinement: reciprocal-merge conversions are the same
per-edge-policy-record lever. Next dup-heavy candidates: MultiDiGraph→MultiGraph `to_undirected` (digraph.rs
~7154 pyo3 / core), other reciprocal-collapse conversions.
