# br-r37-c1-gnmdigraphbatch — gnm_random_digraph batch-by-index (directed seen-set)

Status: **SHIP.** 6.54x, byte-identical. clippy clean. **First win of the directed sub-vein.**

## The target

`gnm_random_digraph(n, m, seed)` is a rejection sampler: it draws `(u, v)` until `m` distinct directed
edges are accepted, rejecting on `u == v` or when the directed edge already exists. The rejection test
was a per-draw `graph.has_edge(&node_labels[u], &node_labels[v])` on the String-keyed adjacency, and each
accept did a per-edge `add_edge`. This is the **directed analog of the shipped undirected gnm win**
(`922444175`, 8.55x).

## The lever

Replace the per-draw `has_edge` with an integer **directed** seen-set (`HashSet<(usize,usize)>`, keyed on
`(u, v)` with **no** canonicalization — direction matters), collect the accepted `(u, v)` index pairs,
and batch-insert with `DiGraph::extend_existing_index_edges_with_attrs_unrecorded` (empty `AttrMap` per
edge = unweighted `add_edge`).

## Byte-identical argument

The seen-set mirrors `has_edge` exactly at every step (both start empty; both gain `(u,v)` precisely when
an edge is accepted), so the reject decisions — and therefore the RNG draw sequence and the accepted-edge
sequence — are identical to the per-edge loop. `extend_existing_index_edges_with_attrs_unrecorded`
inserts `(source,target)` and pushes `succ_indices[source]`/`pred_indices[target]` in insertion order,
matching `add_edge`; an empty `AttrMap` equals the unweighted `add_edge`'s stored attrs. **Verified
profile-first** (before the production edit): `gnm_digraph_batch_ab` parity asserts across 4 configs —
including the dense `(200, 20000)` with heavy `has_edge` rejection — all `assert_eq!(edges_ordered_borrowed
+ nodes_ordered)` pass. Suite exact-vs-nx: `gnm_random_digraph_matches_networkx_seeded_example` passes.

## Median A/B (paired-interleaved, one binary, NULL control)

`cargo test --release -p fnx-generators --lib gnm_digraph_batch_ab -- --ignored --nocapture`

gnm_random_digraph(1000, 300000) (1000 nodes, 300000 directed edges, ~30% dense). 61 rounds. Ratio =
base/cand, **>1 = batch faster**.

| row | median | win_rate | p5_p95 |
|-----|-------:|---------:|--------|
| `BATCH_vs_string` | **6.5368x** | 61/61 | [5.2052, 8.1557] |
| `NULL_batch_vs_batch` | 0.9902x | 26/61 | [0.8284, 1.2817] |

Decisive: candidate p5 (5.21) ~4.1x above the NULL p95 (1.28); all 61 rounds won. The win is the dropped
per-draw `has_edge` (String-keyed) plus the batch insert; the RNG sampling cost is common to both arms.

## Files

- Production: `crates/fnx-generators/src/lib.rs` — `gnm_random_digraph`.
- Test-only: `gnm_digraph_batch_ab` A/B.

## Vein status

Twenty-first engine-level generator batch win, and the **first of the directed sub-vein** — it proves
`DiGraph::extend_existing_index_edges_with_attrs_unrecorded` is byte-identical to per-edge `add_edge`
(direction + dedup + empty AttrMap), opening the directed generators
(`gnp_random_digraph`, `fast_gnp_random_digraph` complete branch, `random_uniform_k_out_digraph`, …).
Next: profile `gnp_random_digraph` (dense/insertion-bound?).
