# br-r37-c1-sudokubatch — sudoku_graph batch-by-index (seen-set)

Status: **SHIP.** 8.39x, byte-identical. clippy clean.

## The target

`sudoku_graph(n)` builds the sudoku constraint graph on `n^4` nodes: a clique over each row, each column,
and each n×n box. The native builder emitted these via per-edge `add_edge(node_labels[…].clone(), …)`;
all nodes pre-exist (`graph_with_n_nodes`). Deterministic (no RNG) → insertion-bound.

A cell shares its row **and** its box with some peers, so the row-clique and box-clique passes emit
**duplicate** pairs — this is a seen-set member.

## The lever

Collect the `(u, v)` INDEX pairs with a gnm-style integer seen-set — canonical `(min,max)` key,
skip-if-seen, first-occurrence order — in the SAME emission order (rows, then columns, then boxes), then
one `Graph::extend_existing_index_edges_unrecorded`. No self-loops.

## Byte-identical argument

The seen-set reproduces `add_edge`'s dedup exactly (a simple graph ignores a repeated edge, keeping the
first occurrence). `extend_existing_index_edges_unrecorded` matches `add_edge`'s endpoint canonicalization
and `adj_indices` order (dedup handling proven by the sibling circulant win). **Verified profile-first**
(before the production edit): `sudoku_batch_ab` parity asserts across n = 2, 3, 4, 9 (all dedup-heavy) —
all `assert_eq!(edges_ordered_borrowed + nodes_ordered)` pass. Suite exact-vs-nx:
`sudoku_graph_default_order_matches_networkx_counts_and_neighbors` passes.

## Median A/B (paired-interleaved, one binary, NULL control)

`cargo test --release -p fnx-generators --lib sudoku_batch_ab -- --ignored --nocapture`

sudoku(9) (6561 nodes, ~735k edges). 61 rounds. Ratio = base/cand, **>1 = batch faster**.

| row | median | win_rate | p5_p95 |
|-----|-------:|---------:|--------|
| `BATCH_vs_string` | **8.3895x** | 61/61 | [5.5274, 9.9168] |
| `NULL_batch_vs_batch` | 0.9990x | 28/61 | [0.8638, 1.1066] |

Decisive: candidate p5 (5.53) ~5.0x above the NULL p95 (1.11); all 61 rounds won.

## Files

- Production: `crates/fnx-generators/src/lib.rs` — `sudoku_graph`.
- Test-only: `sudoku_batch_ab` A/B.

## Vein status

Twentieth engine-level generator batch win — **the engine-level per-edge-`add_edge` generator vein is now
fully mined** (20 wins this session, all byte-identical, all >null). Vein: gnp 13.20x, gnm 8.55x,
complete_multipartite 13.24x, turan 16.22x, ring_of_cliques 19.94x, windmill 18.63x, caveman 3.86x,
barbell 16.92x, lollipop 13.29x, tadpole 7.10x, hkn_harary 19.86x, hypercube 6.47x, wheel 24.28x,
binomial_tree 6.96x, grid_2d 4.08x, circulant 17.37x, generalized_petersen 6.13x, hnm_harary 8.24x,
grid_graph 5.47x, sudoku 8.39x; barabasi 1.04x surfaced (sampling-bound, the only non-win). Next frontiers:
DIRECTED generators (need a DiGraph index-batch inserter) or upgrading ladder/circular_ladder from the
String-pair `extend_edges_unrecorded` to the index-pair inserter (drop name-hashes, modest).
