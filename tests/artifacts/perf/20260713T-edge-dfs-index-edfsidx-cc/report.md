# br-r37-c1-edfsidx — edge_dfs / edge_dfs_directed: String/alloc-heavy edge-DFS → integer-index

Status: **SHIP.** 7.8588x, byte-identical, STRICT gate. Biggest single-pass String→int win of the sweep.

## The target

`edge_dfs(graph, source)` / `edge_dfs_directed(digraph, source)` yield edges in DFS order. The old kernels were
extraordinarily allocation-heavy:

- **cloned every node's neighbours into a `Vec<String>`** (`graph.neighbors(&u).map(String::from).collect()`)
  and pushed it onto the DFS stack — a full String-copy of the adjacency per node visit;
- keyed `visited_edges` on `(String, String)` and `visited_nodes` on `String`;
- cloned `u`/`v` names on every edge step.

## The lever

Push borrowed integer adjacency rows (`&[usize]` from `neighbors_indices`/`successors_indices`, no allocation)
onto the stack, dedup edges via `(usize, usize)` and nodes via `Vec<bool>`; node names materialise only into
the O(|E|) result.

## Byte-identical argument

The undirected edge key `(min, max)` (and the directed key `(u, v)`) canonicalises the same by INDEX as it did
by NAME, so `visited_edges` dedups the identical set of edges either way; `neighbors_indices`/
`successors_indices` preserve the String iterators' order, so the DFS visits neighbours in the same order →
the identical edge-DFS sequence of `(u_name, v_name)` pairs (order-sensitive output). A `source` not in the
graph → `get_node_index == None` → empty result (matching the old empty-neighbours path). Verified: the A/B
asserts `old_fn(&g,"0") == super::edge_dfs(&g,"0")` (order-sensitive) AND
`old_dir(&dg,"0") == super::edge_dfs_directed(&dg,"0")`; `test_edge_dfs_path`, `test_edge_dfs_directed` pass.

## Median A/B (full function, paired-interleaved, one binary, NULL control)

`cargo test --release -p fnx-algorithms --lib edge_dfs_idx_ab -- --ignored --nocapture`

Dense undirected circulant (2000 nodes, degree 40 → ~40k edges). 61 rounds. Ratio = String / index, **>1 =
index faster**.

| row | median | win_rate | p5_p95 |
|-----|-------:|---------:|--------|
| `INDEX_vs_string` | **7.8588x** | 61/61 | [5.7016, 9.8727] |
| `NULL_index_vs_index` | 0.9907x | 28/61 | [0.8113, 1.2263] |

Decisive: candidate p5 (5.70) is ~4.6x above the null p95 (1.23) — clears the STRICT gate by a wide margin;
all 61 rounds won; null centred on 1.0. Bigger than the other single-pass wins (bfs_layers 4-5x, descendants
2.8x) because edge_dfs cloned the WHOLE adjacency into `Vec<String>` per node visit — the removed allocation
dwarfs the visited-probe savings.

## Files

- Production: `crates/fnx-algorithms/src/lib.rs` — `edge_dfs`, `edge_dfs_directed`.
- Test-only: `edge_dfs_idx_ab` A/B (times edge_dfs + parity-asserts edge_dfs_directed).

## Notes

- Stack holds borrowed `&[usize]` adjacency rows (immutable borrows of `graph`, valid for the fn) — no
  re-fetch, no clone. The alloc-heaviest traversals give the biggest String→int wins.
