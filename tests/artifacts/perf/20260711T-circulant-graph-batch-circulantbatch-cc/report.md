# br-r37-c1-circulantbatch — circulant_graph batch-by-index edge insertion (seen-set)

Status: **SHIP.** 17.37x, byte-identical. clippy clean.

## The target

`circulant_graph(n, offsets)` connects each node to `node ± offset` for every offset. The native builder
emitted, per `(node, offset)`, a **backward** edge then a **forward** edge via per-edge
`add_edge(node_labels[…].clone(), …)`; all nodes pre-exist (`graph_with_n_nodes`). Deterministic (no RNG)
→ insertion-bound.

Unlike the earlier clean generators, circulant's emission **always duplicates** every edge (the forward
edge from `node` equals the backward edge from `node+offset`), and it can emit **self-loops** (offset 0)
and coincident forward==backward (offset n/2). So a raw index batch would double every edge — this is the
first member of the **seen-set sub-vein**.

## The lever

Collect the `(node, target)` INDEX pairs with a gnm-style integer seen-set — canonical `(min,max)` key,
skip-if-already-seen, first-occurrence order — in the SAME emission order (backward then forward), then
one `Graph::extend_existing_index_edges_unrecorded`. The seen-set exactly reproduces `add_edge`'s dedup
(a simple graph ignores a repeated edge, keeping the first occurrence's adjacency position).

## Byte-identical argument

`add_edge` on a simple graph is a no-op for a duplicate edge → the adjacency order is set by first
insertion; the seen-set pushes exactly the first occurrence of each canonical pair, in emission order, so
the resulting `edges` vec == the effective add_edge sequence. `extend_existing_index_edges_unrecorded`
matches `add_edge`'s endpoint canonicalization, `adj_indices` order, **and** self-loop handling.
**Verified empirically** (profile-first, before the production edit): the `circulant_batch_ab` parity
asserts cover 6 configs including the risky `(100,[50])` offset==n/2, `(7,[0])` self-loops, and
`(7,[0,2])` self-loops+normal — all `assert_eq!(edges_ordered_borrowed + nodes_ordered)` pass. The suite's
exact-vs-nx tests `…_complete_case`, `…_cycle_case`, `…_empty_graph_case`, and `…_self_loop_case` all pass.

## Median A/B (paired-interleaved, one binary, NULL control)

`cargo test --release -p fnx-generators --lib circulant_batch_ab -- --ignored --nocapture`

circulant(10000, [1,2,3,4,5]) (10000 nodes, 50000 edges). 61 rounds. Ratio = base/cand, **>1 = batch
faster**.

| row | median | win_rate | p5_p95 |
|-----|-------:|---------:|--------|
| `BATCH_vs_string` | **17.3655x** | 61/61 | [13.3293, 20.3729] |
| `NULL_batch_vs_batch` | 1.0016x | 32/61 | [0.7957, 1.1782] |

Decisive: candidate p5 (13.33) ~11.3x above the NULL p95 (1.18); all 61 rounds won. The seen-set's
`HashSet` overhead is dwarfed by the dropped per-edge String clones/hashes/policy.

## Files

- Production: `crates/fnx-generators/src/lib.rs` — `circulant_graph`.
- Test-only: `circulant_batch_ab` A/B.

## Vein status

Sixteenth engine-level generator batch win — and the **first of the seen-set sub-vein**. It proves
`extend_existing_index_edges_unrecorded` handles self-loops + dedup byte-identically vs both the per-edge
path and networkx, which de-risks the remaining seen-set members (`generalized_petersen` k=n/2,
`hnm_harary`, `sudoku_graph`, `grid_graph` size-1-periodic). Vein: gnp 13.20x, gnm 8.55x,
complete_multipartite 13.24x, turan 16.22x, ring_of_cliques 19.94x, windmill 18.63x, caveman 3.86x,
barbell 16.92x, lollipop 13.29x, tadpole 7.10x, hkn_harary 19.86x, hypercube 6.47x, wheel 24.28x,
binomial_tree 6.96x, grid_2d 4.08x, circulant 17.37x shipped; barabasi 1.04x surfaced.
