# br-r37-c1-tadpolebatch — tadpole_graph batch-by-index edge insertion

Status: **SHIP.** 7.10x, byte-identical. clippy clean.

## The target

`tadpole_graph(m, n)` builds a cycle of `m` nodes with a path tail of `n` nodes attached by one
connection edge. The native engine builder used per-edge
`add_edge(node_labels[left].clone(), node_labels[right].clone())` for every cycle/connection/tail
edge; all nodes pre-exist (`graph_with_n_nodes`). Deterministic (no RNG) → insertion-bound.

tadpole is **sparse** (cycle m + connection + tail = m+n edges over m+n nodes), so a priori the
per-node construction cost could dilute the per-edge batch win. **PROFILE-FIRST**: the batch-vs-string
A/B was run at the max size (m+n = 100k) BEFORE any production edit; it cleared the null decisively
(7.10x — the per-edge String overhead dominates node creation even at edges≈nodes), so the production
edit was then applied.

## The lever

Collect the `(left, right)` INDEX pairs in the SAME order (cycle, connection, tail) and batch-insert
with `Graph::extend_existing_index_edges_unrecorded`. Drops per accepted edge: 2 String clones +
2 name→index hashes + 1 runtime-policy record.

## Byte-identical argument

Nodes pre-exist. Cycle edges `(node, (node+1) % m)` for `m>=2` are all unique with no self-loops —
including the wrap edge `(m-1, 0)`, which is pushed in the same argument order as the per-edge
`add_edge(node_labels[m-1], node_labels[0])` so its adjacency insertion + name-order endpoint
canonicalization are identical. The connection edge `(m-1, m)` and tail edges `(m..m+n)` bridge/span
disjoint index ranges → unique. Verified three ways:
- A/B parity: `assert_eq!(batch.edges_ordered_borrowed(), string.edges_ordered_borrowed())` +
  `nodes_ordered` on `tadpole(90000, 10000)`.
- Suite exact-vs-nx: `tadpole_graph_matches_networkx_cycle_case` (n=0 branch) and
  `tadpole_graph_matches_networkx_cycle_plus_path_case` (n>0 branch) both pass.
- `tadpole_graph_rejects_m_below_two_like_networkx` (guard path unchanged) passes.

## Median A/B (paired-interleaved, one binary, NULL control)

`cargo test --release -p fnx-generators --lib tadpole_batch_ab -- --ignored --nocapture`

tadpole(90000, 10000) (100000 nodes, 100000 edges). 61 rounds. Ratio = base/cand, **>1 = batch faster**.

| row | median | win_rate | p5_p95 |
|-----|-------:|---------:|--------|
| `BATCH_vs_string` | **7.0988x** | 61/61 | [5.2328, 8.4099] |
| `NULL_batch_vs_batch` | 0.9943x | 29/61 | [0.8373, 1.1833] |

Decisive: candidate p5 (5.23) ~4.4x above the NULL p95 (1.18); all 61 rounds won.

## Files

- Production: `crates/fnx-generators/src/lib.rs` — `tadpole_graph`.
- Test-only: `tadpole_batch_ab` A/B.

## Vein status

Tenth engine-level generator batch win (gnp 13.20x, gnm 8.55x, complete_multipartite 13.24x, turan
16.22x, ring_of_cliques 19.94x, windmill 18.63x, caveman 3.86x, barbell 16.92x, lollipop 13.29x,
tadpole 7.10x); barabasi 1.04x surfaced (sampling-bound). This shows the batch win holds even for SPARSE
generators (edges≈nodes) — the per-edge String clone/hash/policy overhead dominates, not construction.
Remaining candidates need dedup (sudoku, duplicate row/box pairs) or are degenerate p>=1.0 edge-cases;
`complete_graph` is already a native constructor.
