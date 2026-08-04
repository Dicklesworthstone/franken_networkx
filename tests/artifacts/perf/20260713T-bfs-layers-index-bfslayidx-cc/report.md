# br-r37-c1-bfslayidx — bfs_layers: String-keyed BFS → integer-index BFS

Status: **SHIP.** 4.2209x, byte-identical, STRICT gate.

## The target

`bfs_layers(graph, source)` does a single-source BFS returning the node names layer by layer. The kernel kept
`visited` as a `HashSet<&str>` and called `graph.neighbors(node)` — a fresh `Vec<&str>` allocation — per node,
so it paid a String hash on every visited probe across O(|E|) edge scans plus O(|V|) neighbour-Vec allocations.

## The lever

Resolve `source` to its index once (`get_node_index`), then BFS over node INDICES with `neighbors_indices`
(no per-node Vec alloc) and a `Vec<bool>` visited (O(1) probe). Only the per-layer output materialises names
(`nodes[i].to_owned()`), which is O(|V|) total — NOT diluting like an O(|V|²) String-keyed output would.

## Byte-identical argument

Node index i == `nodes_ordered()` position, and `neighbors_indices` yields neighbours in the same order as
`neighbors`, so the per-layer discovery order (and thus each layer's node ordering) is unchanged, and the names
emitted (`nodes[i]`) are the same. Verified: the A/B asserts `old_fn(&g, "0") == super::bfs_layers(&g, "0")`
(inline String BFS vs the shipped index BFS) on a dense 3000-node graph; `bfs_layers_test` + `bfs_layers_directed_dag`
pass.

## Median A/B (full function, paired-interleaved, one binary, NULL control)

`cargo test --release -p fnx-algorithms --lib bfs_layers_idx_ab -- --ignored --nocapture`

Dense circulant (3000 nodes, degree 100 → ~150k edges) so the O(|E|) visited probes + per-node neighbour-Vec
allocs dominate the O(|V|) name output. 61 rounds. Ratio = String / index, **>1 = index faster**.

| row | median | win_rate | p5_p95 |
|-----|-------:|---------:|--------|
| `INDEX_vs_string` | **4.2209x** | 60/61 | [3.2006, 5.5088] |
| `NULL_index_vs_index` | 0.9883x | 29/61 | [0.8160, 1.3541] |

Decisive: candidate p5 (3.20) is well above the null p95 (1.35) — clears the STRICT gate; null centred on 1.0.
A solid SINGLE-PASS win (not 30x like the multi-round girth/voterank) because it's one BFS — but NOT diluted,
because the output is O(|V|) names, not an O(|V|²) String-keyed structure (contrast the rejected
transitive_closure).

## Files

- Production: `crates/fnx-algorithms/src/lib.rs` — `bfs_layers`.
- Test-only: `bfs_layers_idx_ab` A/B.

## Notes

- SHARED-FILE DISCIPLINE: a peer had concurrent uncommitted `is_distance_regular` work in the same file.
  Committed ONLY my two hunks via a filtered `git apply --cached`; peer hunks left untouched.
- The bfs_layers FAMILY (bfs_layers_multi / _multi_with_parents / bfs_layers_directed_multi) is the same
  String-keyed single-pass shape — natural next candidates (each O(|V|) output, so not diluted).
