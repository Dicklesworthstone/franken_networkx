# br-r37-c1-fcycundidx — find_cycle_undirected adjacency-build integer swap

Status: **SHIP.** 2.32x, byte-identical. Undirected sibling of `find_cycle_directed` (br-r37-c1-fcycidx). My
change clippy-clean (crate has pre-existing peer lint debt, untouched).

## The target

`find_cycle_undirected(graph)` (fnx-algorithms) builds an integer adjacency `Vec<Vec<usize>>` once, then runs
a fully-integer parent-tracking DFS. The adjacency build (setup) went through node names: `node_to_idx` +
`graph.neighbors(node)` (a `Vec<&str>` alloc per node) + `node_to_idx.get(nbr)` (a String re-hash per edge),
each row `sort_unstable`'d.

## The lever

Build each `adj[i]` from `graph.neighbors_indices(i)` (zero-alloc `&[usize]`) directly, dropping the
`Vec<&str>` allocations, the `node_to_idx` map, and the `O(E)` `node_to_idx.get` re-hashes. Each row still
`sort_unstable`'d.

## Byte-identical argument

Every neighbour is a graph node, so the old `node_to_idx.get(nbr)` was always `Some` — `adj[i]` is the
identical set of neighbour indices as `neighbors_indices(i)`. Both are `sort_unstable`'d, so the sorted
adjacency is identical, and the DFS over it finds the **same cycle in the same order**. Verified: A/B
**differential parity** `assert_eq!(old, new)` (inline old-`node_to_idx`+`neighbors` setup vs new-
`neighbors_indices` setup, shared DFS) passed before timing; the 5 find_cycle suite tests pass, including
`test_find_cycle_undirected_exists` (pins the exact cycle) and `test_find_cycle_undirected_tree` (None).

## Median A/B (paired-interleaved, one binary, NULL control)

`cargo test --release -p fnx-algorithms --lib find_cycle_undirected_idx_ab -- --ignored --nocapture`

50000-node circulant (degree 20). A dense graph finds a cycle almost immediately, so the full-adjacency
**setup** (the part optimized) dominates the runtime. 61 rounds. Ratio = string/index, **>1 = index faster**.

| row | median | win_rate | p5_p95 |
|-----|-------:|---------:|--------|
| `INT_vs_string` | **2.3166x** | 61/61 | [2.0649, 2.6204] |
| `NULL_int_vs_int` | 0.9952x | 29/61 | [0.9068, 1.0802] |

Decisive: candidate p5 (2.06) ~1.9x above the NULL p95 (1.08); all 61 rounds won.

## Clippy note

My change is clippy-clean (0 findings in production ~28626-28638 / test ~71326-71471, grep-verified). The
crate has 12 pre-existing clippy `-D warnings` errors in peer/committed code — left untouched per
shared-checkout discipline.

## Files

- Production: `crates/fnx-algorithms/src/lib.rs` — `find_cycle_undirected`.
- Test-only: `find_cycle_undirected_idx_ab` A/B.

## Vein status

Seventh "name-keyed → integer" sub-family win; the find_cycle pair (directed + undirected) is now fully
integer in its adjacency build. Next of the "mostly-integer + name-residual" flavour: `generic_bfs_edges`,
`snap_aggregation` (both matched the grep — verify output order-independence before converting).
