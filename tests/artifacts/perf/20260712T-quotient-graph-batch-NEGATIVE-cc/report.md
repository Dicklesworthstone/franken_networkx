# br-r37-c1-quotientbatch — quotient_graph batch — REJECTED (below null)

Status: **REJECT / SURFACE.** Byte-identical but below the null floor. Production reverted.

## What was tried

`quotient_graph(graph, partition)` collapses nodes into partition blocks and adds one edge per distinct
inter-block pair. It ALREADY has a `seen_edges: HashSet<(usize,usize)>` that dedups inter-block edges to
the first-seen canonical `(bi<bj)` pair (self-loops skipped via `bi != bj`), then adds each unique block
edge via a per-edge `add_edge`. The lever: keep the seen_edges dedup, collect the unique block edges, and
insert with one `Graph::extend_edges_unrecorded`.

## Why it was rejected

The change is **byte-identical** (A/B parity `assert_eq!(edges_ordered_borrowed + nodes_ordered)` passed on
K300 partitioned into 100 blocks), but the median A/B is **below the null floor**:

| row | median | win_rate | p5_p95 |
|-----|-------:|---------:|--------|
| `BATCH_vs_string` | 1.1103x | 45/61 | [0.8564, 1.4787] |
| `NULL_batch_vs_batch` | 1.0161x | 39/61 | [0.9363, 1.1757] |

Candidate p5 (0.86) < null p95 (1.18); win_rate 45/61 barely above null 39/61. **Amdahl**: the batch only
saves the per-edge policy record on the ~4950 *unique block* edges, but the loop scans all `|E|` input
edges (44850 for K300) and the `seen_edges` HashSet insert per input edge dominates — that work is common
to both arms. So the batchable fraction is too small to clear the null. Unlike the dense result-builders
(products, complements, line graphs — where every input edge becomes a result edge), quotient collapses
`|E|` inputs into `O(blocks²)` outputs, so the insertion is a minority of the total.

## Outcome

Production edit and A/B test **reverted** — `git diff crates/fnx-algorithms/src/lib.rs` is empty. Only this
negative-ledger entry is committed. Lesson: result-builders whose output edge count is much smaller than
their input-edge scan (`quotient_graph`, and likely `condensation`) are Amdahl-limited by the scan/dedup;
the batch-insert lever needs output ≈ `|E|` to clear the null.
