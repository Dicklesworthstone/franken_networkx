# br-r37-c1-barbellbatch — barbell_graph INDEX-pair edge batch-insert

Status: **SHIP.** 23.10x, byte-identical. My change clippy-clean (crate has pre-existing peer lint debt,
untouched).

## The target

`barbell_graph(n1, n2)` (fnx-algorithms) — the barbell graph: two complete graphs Kₙ₁ (the "bells") joined
by a path of `n2` nodes (the "bar"), `2·n1 + n2` nodes total (named `"0".."total-1"` via `gen_nodes`). Four
per-edge phases: first Kₙ₁ clique, the path, the second Kₙ₁ clique, and the two clique↔path connectors —
all via `gen_edge(&mut g, i, j)`.

## The lever — INDEX batch (the `gen_edge` sub-lever)

Node index `i` *is* the loop variable. Collect all edges (both cliques, path, connectors; same order) as
`(i, j)` **usize index pairs** and insert with one `Graph::extend_existing_index_edges_unrecorded` —
dropping both `to_string()` allocs, the name→index hashes, and the per-edge policy record. The two cliques
dominate the edge count → dense-few-node.

## Byte-identical argument

Every edge has `source < target` (cliques `i<j`, path `n1+i < n1+i+1`, connectors `n1-1<n1` and
`n1+n2-1<n1+n2`), so each collected pair is a unique non-self-loop edge; the loops read only their own vars
(never `g`). The `if n2>0 / else` connector branch is preserved verbatim in the batch.
`extend_existing_index_edges_unrecorded` dedups on `canon_pair`, canonicalizes `edge_index_endpoints` by node
**name** (identical string comparison to `add_edge`), and pushes `adj_indices` in the given order, exactly as
the per-edge loop. All nodes are pre-added by `gen_nodes`. Verified: A/B parity `assert_eq!
(edges_ordered_borrowed + nodes_ordered)` on B(180,5) (365 nodes, ~32226 edges) passed before timing; suite
test `test_barbell_graph` passes.

## Median A/B (paired-interleaved, one binary, NULL control)

`cargo test --release -p fnx-algorithms --lib barbell_graph_batch_ab -- --ignored --nocapture`

B(180,5): 365 nodes, ~32226 edges (two K₁₈₀ bells + 5-node bar). 61 rounds. Ratio = base/cand, **>1 = batch
faster**.

| row | median | win_rate | p5_p95 |
|-----|-------:|---------:|--------|
| `BATCH_vs_string` | **23.0995x** | 61/61 | [16.3864, 33.3111] |
| `NULL_batch_vs_batch` | 0.9985x | 27/61 | [0.9012, 1.1384] |

Decisive: candidate p5 (16.39) ~14x above the NULL p95 (1.14); all 61 rounds won.

## Clippy note

My change is clippy-clean (0 findings in production ~33109-33137 / test ~69618-69737, grep-verified). The
crate has 12 pre-existing clippy `-D warnings` errors in peer/committed code — left untouched per
shared-checkout discipline.

## Files

- Production: `crates/fnx-algorithms/src/lib.rs` — `barbell_graph`.
- Test-only: `barbell_graph_batch_ab` A/B.

## Vein status

Twenty-ninth result-builder batch win; 9th in the `gen_edge` index-batch gold seam (hypercube 11.55x,
multipartite 28.34x, bipartite 31.65x, turan 25.42x, windmill 17.90x, paley 26.47x, lollipop 21.28x, barbell
23.10x). This exhausts the clique-dominated dense builders. Remaining reachable `gen_edge` generators are
sparse (`circulant_graph` few-offsets, `tadpole_graph`, ladders, trees — lower tier) or tiny fixed
named-graphs (petersen/chvatal/etc — negligible).
