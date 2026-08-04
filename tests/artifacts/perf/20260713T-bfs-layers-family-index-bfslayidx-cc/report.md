# br-r37-c1-bfslayidx (family) — bfs_layers multi-source family: String-keyed BFS → integer-index BFS

Status: **SHIP.** 5.6188x on `bfs_layers_multi`, byte-identical, STRICT gate. Family follow-up to the single
`bfs_layers` (4.22x, br-r37-c1-bfslayidx).

## The target

Three multi-source BFS-layer functions shared the same String-keyed kernel as `bfs_layers` — `HashSet<&str>`
visited + `graph.neighbors()`/`digraph.successors()` (a fresh `Vec<&str>` allocation per node):

- `bfs_layers_multi(graph, sources)`
- `bfs_layers_directed_multi(digraph, sources)`
- `bfs_layers_multi_with_parents(graph, sources)` (also tracks each node's discovering parent)

(`bfs_layers_directed_multi_with_parents` was already integer-CSR — untouched.)

## The lever

Same as bfs_layers: resolve each source via `get_node_index`, BFS over node INDICES with
`neighbors_indices`/`successors_indices` (no per-node Vec alloc) + a `Vec<bool>` visited. Names (and, for the
parents variant, the discovering parent's name via `nodes[parent_idx]`) are materialised only in the O(|V|)
per-layer output.

## Byte-identical argument

Node index i == `nodes_ordered()` position; `neighbors_indices`/`successors_indices` yield the same order as
the String iterators — so the seed order (sources, valid + unvisited), the per-layer discovery order, the node
names, and (for the parents variant) each node's discovering parent are all unchanged. Verified: the A/B
asserts `old_fn == super::bfs_layers_multi` on a dense 3000-node graph with 3 sources; `bfs_layers_test` +
`bfs_layers_directed_dag` pass. The `_directed_multi` / `_multi_with_parents` conversions are mechanically
identical to the asserted `_multi` (neighbours→successors; parent index→name) — byte-identical by the same
argument.

## Median A/B (full function, paired-interleaved, one binary, NULL control)

`cargo test --release -p fnx-algorithms --lib bfs_layers_multi_idx_ab -- --ignored --nocapture`

Dense circulant (3000 nodes, degree 100 → ~150k edges), 3 sources. 61 rounds. Ratio = String / index, **>1 =
index faster**.

| row | median | win_rate | p5_p95 |
|-----|-------:|---------:|--------|
| `INDEX_vs_string` | **5.6188x** | 61/61 | [4.1514, 6.7604] |
| `NULL_index_vs_index` | 1.0038x | 32/61 | [0.6600, 1.5095] |

Decisive: candidate p5 (4.15) is well above the null p95 (1.51) — clears the STRICT gate; all 61 rounds won;
null centred on 1.0.

## Files

- Production: `crates/fnx-algorithms/src/lib.rs` — `bfs_layers_multi`, `bfs_layers_directed_multi`,
  `bfs_layers_multi_with_parents`.
- Test-only: `bfs_layers_multi_idx_ab` A/B.

## Notes

- SHARED-FILE DISCIPLINE: a peer's `is_distance_regular` work committed mid-turn (HEAD advanced), leaving only
  my hunks in the working tree — verified `git diff` was all bfs_layers content before `git add`.
- bfs_layers family now fully integer-index. The single-pass String→int lever (O(|V|) output → not diluted)
  is confirmed across the family.
