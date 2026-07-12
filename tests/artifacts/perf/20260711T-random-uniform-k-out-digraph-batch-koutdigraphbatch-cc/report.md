# br-r37-c1-koutdigraphbatch — random_uniform_k_out_digraph batch-by-index (directed)

Status: **SHIP.** 4.76x, byte-identical. clippy clean.

## The target

`random_uniform_k_out_digraph(n, k, self_loops, seed)` gives each source node `k` out-edges to `k`
distinct targets sampled uniformly (without replacement) from its candidate set. The native builder did
per-edge `add_edge(node_labels[source].clone(), node_labels[target].clone())`; nodes pre-exist
(`digraph_with_n_nodes`). Deterministic given the seed → insertion-bound.

## The lever

Collect the accepted `(source, target)` INDEX pairs in the SAME order and batch-insert with
`DiGraph::extend_existing_index_edges_with_attrs_unrecorded` (empty `AttrMap` = unweighted `add_edge`).

## Profile-first rationale

Unlike gnm/gnp, this generator has a per-source O(n) candidate build (`uniform_k_out_candidates`, so
O(n²) total) plus the k-sampling, both **common to both arms** — that could have swamped the batch's
per-edge saving. So the A/B was run BEFORE any production edit; it cleared the null decisively (4.76x —
the per-edge insertion overhead on the ~2M edges still dominated), so the edit was applied.

## Byte-identical argument

`python_sample_indices` returns `k` distinct target indices per source → no duplicate edges within a
source; distinct sources give distinct `(source, target)` pairs → no duplicates overall. Self-loops occur
only when `self_loops = true` (the candidate set then includes the source) and are handled byte-identically
(proven by the circulant win). The k-loop never reads the graph, so the accepted-edge sequence is
unchanged. **Verified profile-first**: `kout_digraph_batch_ab` parity asserts across 4 configs —
`(100,10,false)`, `(100,50,true)` (self-loops), `(500,100,false)`, `(2000,1000,false)` — all pass. Suite
exact-vs-nx: `random_uniform_k_out_digraph_matches_networkx_seeded_examples` passes.

## Median A/B (paired-interleaved, one binary, NULL control)

`cargo test --release -p fnx-generators --lib kout_digraph_batch_ab -- --ignored --nocapture`

random_uniform_k_out_digraph(2000, 1000) (2000 nodes, 2000000 directed edges). 61 rounds. Ratio =
base/cand, **>1 = batch faster**.

| row | median | win_rate | p5_p95 |
|-----|-------:|---------:|--------|
| `BATCH_vs_string` | **4.7622x** | 61/61 | [3.3452, 10.1702] |
| `NULL_batch_vs_batch` | 0.9945x | 28/61 | [0.9096, 1.1090] |

Decisive: candidate p5 (3.35) ~3.0x above the NULL p95 (1.11); all 61 rounds won.

## Files

- Production: `crates/fnx-generators/src/lib.rs` — `random_uniform_k_out_digraph`.
- Test-only: `kout_digraph_batch_ab` A/B.

## Vein status

Twenty-third engine-level generator batch win (third directed). Next directed candidates:
`random_uniform_k_out_multidigraph` (MultiDiGraph — needs a MultiDiGraph index inserter check),
`fast_gnp_random_digraph` (p>=1.0 complete branch, edge case). `random_k_out_graph` reads/updates mutable
preferential weights mid-loop → NOT batchable.
