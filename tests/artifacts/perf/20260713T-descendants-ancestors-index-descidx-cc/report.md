# br-r37-c1-descidx — descendants / ancestors: String-keyed BFS → integer-index BFS

Status: **SHIP.** 2.8024x on `descendants`, byte-identical, STRICT gate. Single-pass String→int on a pair with
O(|V|) (order-independent set) output.

## The target

`descendants(digraph, node)` (forward reachability) and `ancestors(digraph, node)` (backward reachability) each
ran a single BFS keyed on `HashSet<&str>` visited + `successors()`/`predecessors()` (a fresh `Vec<&str>`
allocation per node) — a String hash on every visited probe across O(|E|) edge scans. Both return a
`HashSet<String>` (order-independent).

## The lever

Resolve `node` via `get_node_index`, BFS over node INDICES with `successors_indices`/`predecessors_indices`
(no per-node Vec alloc) + a `Vec<bool>` visited (O(1) probe). Node names are materialised only into the
O(|V|) result set.

## Byte-identical argument

The result is a SET, so BFS order is irrelevant; the same nodes reachable from (resp. to) `node` via ≥1 step,
with `node` itself excluded (it is marked visited before the walk, exactly as the old kernel inserted it
first). `get_node_index(node) == None` ⟺ `!has_node(node)` → empty set. Verified: the A/B asserts
`old_fn(&g, "0") == super::descendants(&g, "0")`, AND both conversions pass their **networkx golden tests** —
`descendants_at_distance_directed_matches_networkx_golden_layers`, `ancestors_matches_networkx_branching_golden_sets`,
plus `descendants_{leaf,test}`, `ancestors_{root,test}` (9 tests total).

## Median A/B (full function, paired-interleaved, one binary, NULL control)

`cargo test --release -p fnx-algorithms --lib descendants_idx_ab -- --ignored --nocapture`

Dense forward directed graph (3000 nodes, out-degree 50 → descendants(0) = all other nodes). 61 rounds. Ratio =
String / index, **>1 = index faster**.

| row | median | win_rate | p5_p95 |
|-----|-------:|---------:|--------|
| `INDEX_vs_string` | **2.8024x** | 61/61 | [2.4039, 3.2080] |
| `NULL_index_vs_index` | 0.9735x | 21/61 | [0.8751, 1.1328] |

Decisive: candidate p5 (2.40) is well above the null p95 (1.13) — clears the STRICT gate; all 61 rounds won;
null centred on 1.0. Smaller than bfs_layers (4-5x) because the `HashSet<String>` result construction (O(|V|)
String inserts) is a bigger fraction of the total than a `Vec<Vec<String>>` — still comfortably above the bar.

## Files

- Production: `crates/fnx-algorithms/src/lib.rs` — `descendants`, `ancestors`.
- Test-only: `descendants_idx_ab` A/B.

## Notes

- SHARED-FILE DISCIPLINE: a peer's `local_bridges_list` work was uncommitted in the same file. Committed ONLY
  my 3 hunks via a filtered `git apply --cached`; peer hunks left untouched.
- Single-pass String→int BFS with O(|V|) output continues to pay (bfs_layers 4-5x, descendants/ancestors 2.8x).
  `ancestors` counterpart converted too (mirror). Next same-shape: bfs_predecessors/bfs_successors (return
  node lists), dfs_edges/bfs_edges (edge lists, O(|V|) for a tree walk).
