# br-r37-c1-fcycidx — find_cycle_directed adjacency-build integer swap

Status: **SHIP.** 2.46x, byte-identical. Same "mostly-integer + name-residual" flavour as `immediate_
dominators`. My change clippy-clean (crate has pre-existing peer lint debt, untouched).

## The target

`find_cycle_directed(graph)` (fnx-algorithms) builds an integer adjacency `Vec<Vec<usize>>` once, then runs a
fully-integer colour DFS to find a cycle. The adjacency build (setup) went through node names:
`node_to_idx` + `graph.successors(node)` (a `Vec<&str>` alloc per node) + `node_to_idx.get(s)` (a String
re-hash per edge), each row then `sort_unstable`.

## The lever

Build each `adj[i]` from `graph.successors_indices(i)` (zero-alloc `&[usize]`) directly, dropping the
`Vec<&str>` allocations, the `node_to_idx` map, and the `O(E)` `node_to_idx.get` re-hashes. Each row is still
`sort_unstable`'d.

## Byte-identical argument

Every successor is a graph node, so the old `node_to_idx.get(s)` was always `Some` — `adj[i]` is the
identical set of successor indices as `successors_indices(i)`. Both are then `sort_unstable`'d, so the sorted
adjacency is identical, and the DFS over the sorted adjacency finds the **same cycle in the same order**.
Verified: A/B **differential parity** `assert_eq!(old, new)` (inline old-`node_to_idx`+`successors` setup vs
new-`successors_indices` setup, shared DFS) passed before timing; the 5 find_cycle suite tests pass, including
`test_find_cycle_directed_exists` (which pins the exact cycle returned) and `test_find_cycle_directed_dag`
(None).

## Median A/B (paired-interleaved, one binary, NULL control)

`cargo test --release -p fnx-algorithms --lib find_cycle_directed_idx_ab -- --ignored --nocapture`

10000-node forward DAG (node i → i+1..i+5, no cycle → full setup + full DFS traversal). 61 rounds. Ratio =
string/index, **>1 = index faster**.

| row | median | win_rate | p5_p95 |
|-----|-------:|---------:|--------|
| `INT_vs_string` | **2.4619x** | 61/61 | [2.0907, 3.5928] |
| `NULL_int_vs_int` | 1.0089x | 37/61 | [0.8718, 1.1460] |

Decisive: candidate p5 (2.09) ~1.8x above the NULL p95 (1.15); all 61 rounds won.

## Clippy note

My change is clippy-clean (0 findings in production ~28562-28575 / test ~71182-71325, grep-verified). The
crate has 12 pre-existing clippy `-D warnings` errors in peer/committed code — left untouched per
shared-checkout discipline.

## Files

- Production: `crates/fnx-algorithms/src/lib.rs` — `find_cycle_directed`.
- Test-only: `find_cycle_directed_idx_ab` A/B.

## Vein status

Sixth "name-keyed → integer" sub-family win, second of the "mostly-integer + name-residual" flavour (after
imdomint). Next: `find_cycle_undirected` (28621) is almost certainly the same adjacency-build residual;
`generic_bfs_edges` and `snap_aggregation` also matched the grep (verify order-independence first).
