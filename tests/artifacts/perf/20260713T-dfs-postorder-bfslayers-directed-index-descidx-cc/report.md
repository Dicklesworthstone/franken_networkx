# br-r37-c1-descidx (dfs) — dfs_postorder_nodes_directed + bfs_layers_directed: String-keyed → integer-index

Status: **SHIP.** 4.7158x on `dfs_postorder_nodes_directed`, byte-identical, STRICT gate.

## The target

Two single-source directed traversals still on the String-keyed shape:

- `dfs_postorder_nodes_directed(digraph, source, depth_limit)` — DFS post-order, `visited: HashSet<&str>` +
  `successors()` (Vec<&str> alloc per node), ORDER-SENSITIVE `Vec<String>` output.
- `bfs_layers_directed(digraph, source)` — the single-source directed member of the bfs_layers family (the
  multi-source ones were converted last commit); `HashSet<&str>` visited + `successors()`.

## The lever

Resolve `source` via `get_node_index`, walk `successors_indices` over node INDICES with a `Vec<bool>` visited
(no per-node Vec alloc); names materialise only into the O(|V|) output. For the DFS, the stack holds
`(node_idx, backtrack, depth)`.

## Byte-identical argument

`successors_indices` yields successors in the same order as `successors()`, so the DFS `.rev()` child-push
order (and hence the post-order sequence) is unchanged; the visited/backtrack/depth logic and the
NetworkX-cutoff rule (`node == source || depth < max_depth`) are untouched. For bfs_layers_directed, the
per-layer discovery order and names are unchanged (same as the bfs_layers family). Verified: the A/B asserts
`old_dfs == super::dfs_postorder_nodes_directed` (ORDER-sensitive) AND `old_bfs_dir ==
super::bfs_layers_directed` on a dense 3000-node directed graph; `dfs_postorder_directed`,
`dfs_postorder_directed_depth_limit_omits_cutoff_node`, `dfs_postorder_nodes_test`, `dfs_postorder_dfspost_ab`,
`bfs_layers_directed_dag` all pass.

## Median A/B (full function, paired-interleaved, one binary, NULL control)

`cargo test --release -p fnx-algorithms --lib dfs_postorder_directed_idx_ab -- --ignored --nocapture`

Dense forward directed graph (3000 nodes, out-degree 50 → deep DFS from 0). 61 rounds. Ratio = String / index,
**>1 = index faster**.

| row | median | win_rate | p5_p95 |
|-----|-------:|---------:|--------|
| `INDEX_vs_string` | **4.7158x** | 61/61 | [3.6062, 5.6638] |
| `NULL_index_vs_index` | 1.0037x | 32/61 | [0.3900, 1.6573] |

Decisive: candidate p5 (3.61) is well above the null p95 (1.66) — clears the STRICT gate; all 61 rounds won;
null centred on 1.0. (Null p95 a touch wide from the postorder Vec-push allocations, but the candidate clears
it comfortably.)

## Files

- Production: `crates/fnx-algorithms/src/lib.rs` — `dfs_postorder_nodes_directed`, `bfs_layers_directed`.
- Test-only: `dfs_postorder_directed_idx_ab` A/B (times the DFS + parity-asserts bfs_layers_directed).

## Notes

- SHARED-FILE DISCIPLINE: a peer's `generic_bfs_edges`/`local_bridges` work was in flight (it committed
  mid-turn). Staged ONLY my 3 hunks via a filtered `git apply --cached`.
- ORDER-SENSITIVE String→int is safe when the index iterator (`successors_indices`) preserves the String
  iterator's order — the DFS post-order is byte-identical. The bfs_layers/descendants/dfs single-pass String→int
  sweep continues to pay ~2.5-5x.
