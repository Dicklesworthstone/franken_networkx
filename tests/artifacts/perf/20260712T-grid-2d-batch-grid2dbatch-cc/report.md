# br-r37-c1-grid2dbatch — grid_2d_graph node + INDEX-pair edge batch-insert

Status: **SHIP.** 12.79x, byte-identical. My change clippy-clean (crate has pre-existing peer lint debt,
untouched).

## The target

`grid_2d_graph(m, n)` (fnx-algorithms) — the 2D grid graph: `m·n` nodes labeled `"r,c"`, each connected to
its right (`"r,c+1"`) and down (`"r+1,c"`) neighbor. Unlike `grid_graph`/the classic generators, it builds
**string labels via `format!`** (not `gen_nodes`/`gen_edge`), and the edge loop recomputes the node label
plus a `right`/`down` label for **every edge** (`~2·m·n` `format!` allocs).

## The lever — index-batch despite string labels

Nodes are added r-major, so node `"r,c"` lands at index `r·n+c`. That lets the edges use the **index batch**
even though the labels are strings: collect the right/down edges as `(i, j)` **usize index pairs** (`i =
r·n+c`, right `= i+1`, down `= i+n`) + one `Graph::extend_existing_index_edges_unrecorded`, which needs **no
labels at all** — eliminating the entire `~2·m·n` per-edge `format!` alloc storm plus the name→index hashes
and policy records. The node build is batched with one `extend_nodes_unrecorded` over the `format!` labels
(the labels are unavoidable, but the per-node policy record is dropped). This is why grid_2d hits 12.79x
where the label-batch `grid_graph` only reached 2.73x: the win here is dropping *the edge labels themselves*,
not just the policy.

## Byte-identical argument

Every edge has `source < target` (right `+1`, down `+n`), so each `(i, j)` is a unique non-self-loop edge;
the loop reads only the loop vars. `extend_nodes_unrecorded` inserts the `"r,c"` labels in the identical
r-major order (so index `r·n+c` names node `"r,c"`, matching the index arithmetic).
`extend_existing_index_edges_unrecorded` dedups on `canon_pair`, canonicalizes `edge_index_endpoints` by node
**name** (identical string comparison to `add_edge` — including e.g. `"9,c"` vs `"10,c"`), and pushes
`adj_indices` in the same right-then-down order as the original loop. Verified: A/B parity `assert_eq!
(edges_ordered_borrowed + nodes_ordered)` on grid_2d(200,200) (40000 nodes, ~79600 edges) passed before
timing; suite test `test_grid_2d_graph` passes.

## Median A/B (paired-interleaved, one binary, NULL control)

`cargo test --release -p fnx-algorithms --lib grid_2d_graph_batch_ab -- --ignored --nocapture`

grid_2d(200,200): 40000 nodes, ~79600 edges. 61 rounds. Ratio = base/cand, **>1 = batch faster**.

| row | median | win_rate | p5_p95 |
|-----|-------:|---------:|--------|
| `BATCH_vs_string` | **12.7913x** | 61/61 | [10.1479, 16.3163] |
| `NULL_batch_vs_batch` | 0.9779x | 24/61 | [0.7682, 1.2189] |

Decisive: candidate p5 (10.15) ~8.3x above the NULL p95 (1.22); all 61 rounds won.

## Clippy note

My change is clippy-clean (0 findings in production ~34010-34035 / test ~69940-70050, grep-verified). The
crate has 12 pre-existing clippy `-D warnings` errors in peer/committed code — left untouched per
shared-checkout discipline.

## Files

- Production: `crates/fnx-algorithms/src/lib.rs` — `grid_2d_graph`.
- Test-only: `grid_2d_graph_batch_ab` A/B.

## Vein status

Thirty-second result-builder batch win. **New insight: a string-labeled generator can still use the 12x
index-batch tier when its node indices are computable from the loop vars** (here `r·n+c`) — the label→index
map is deterministic, so the edges never need labels. This reframes `grid_graph` (n-dim) as a follow-up: its
coordinate labels are also index-computable (`index_to_coords` is invertible), so its String-pair 2.73x batch
could be upgraded to the index-batch tier.
