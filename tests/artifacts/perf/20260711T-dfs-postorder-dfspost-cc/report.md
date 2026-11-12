# br-r37-c1-dfspost — `dfs_postorder_nodes` integer-adjacency iterative DFS

Status: **SHIP.** 6.43x median self-speedup, byte-identical.

## The target

`dfs_postorder_nodes(graph, source, depth_limit)` is one iterative DFS (O(V+E))
returning nodes in postorder. The old kernel kept `visited` as a `HashSet<&str>` and
called `graph.neighbors(node)` (a fresh `Vec<&str>` alloc per pop), pushing
neighbours in reversed adjacency order onto a stack with backtrack markers.

## The lever

`visited` becomes a `Vec<bool>` mark array indexed by node index; the DFS walks
`graph.neighbors_indices(node)` (zero-alloc `&[usize]`) reversed and pushes indices;
`source` is resolved once via `get_node_index` (which also replaces the `has_node`
guard); the postorder output maps `nodes[idx].to_owned()`.

## Byte-identical argument

`neighbors_indices(node)` yields neighbours in the SAME adjacency order as
`neighbors(node)` — NO name-sort anywhere — so `.iter().rev()` pushes the same
children in the same order. The backtrack markers, the depth-limit cutoff
(`node == source_idx || depth < max_depth`, `depth < max_depth`), and the
`visited` semantics are unchanged, so the postorder node sequence is identical.
Output is a node list (no float). Verified in-test with `assert_eq!` against the
String baseline (`dfs_postorder_nodes_orig_string`, `#[cfg(test)]`) for both
`depth_limit = None` and `Some(7)`; the existing
`dfs_postorder_nodes_test` + `..._depth_limit_omits_cutoff_node` unit tests are green.

## Median A/B (paired-interleaved, one binary, NULL control)

`cargo test --release -p fnx-algorithms --lib dfs_postorder_dfspost_ab -- --ignored --nocapture`

Connected pseudo-random graph n=3000 deg~10, 121 rounds. Ratio = base/cand, **>1
means integer faster**.

| row | median | win_rate | p5_p95 |
|-----|-------:|---------:|--------|
| `INT_vs_string` | **6.4271x** | 121/121 | [4.1155, 11.6525] |
| `NULL_int_vs_int` | 1.0083x | 67/121 | [0.7898, 1.3417] |

The lever median (6.43x) clears the NULL floor: candidate p5 (4.12) is ~3x above the
NULL p95 (1.34), and every one of 121 paired rounds won. Higher than a plain
single-BFS win because the DFS pays a `visited` String-set probe per stack push in
the baseline.

## Gates

- clippy `-D warnings`: clean.
- A/B `cargo test --release` ran clean; 4 unit tests + parity (both depth limits) green.
- pyo3 `dfs_postorder_nodes` calls this kernel directly — the win reaches Python.

## Files

- Production: `crates/fnx-algorithms/src/lib.rs` — `dfs_postorder_nodes`.
- Test-only: `dfs_postorder_nodes_orig_string` baseline + `..._dfspost_ab` A/B.
