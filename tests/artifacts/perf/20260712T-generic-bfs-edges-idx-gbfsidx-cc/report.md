# br-r37-c1-gbfsidx — generic_bfs_edges neighbour-iteration integer swap

Status: **SHIP.** 2.42x, byte-identical. My change clippy-clean (crate has pre-existing peer lint debt,
untouched).

## The target

`generic_bfs_edges(graph, source, depth_limit)` (fnx-algorithms) — BFS returning `(v, ni)` edges in traversal
order. Per queue pop it collected neighbours **by name**: `graph.neighbors(nodes[v])` (a `Vec<&str>` alloc) +
`idx.get(nb)` (a String re-hash per edge), filtered to unvisited, then `nbrs.sort()`.

## The lever

Walk `graph.neighbors_indices(v)` (zero-alloc `&[usize]`) directly, dropping the `Vec<&str>` allocation and
the String re-hashes. The `idx` map is kept (used once for the start node). `nbrs.sort()` is unchanged.

## Byte-identical argument (order-safe because it sorts)

Even though the output is an ordered edge list, the BFS **sorts `nbrs` before processing**, so the emitted
order is canonicalised by node index — independent of the neighbour-iteration order. Every neighbour is a
graph node (the old `idx.get(nb)` was always `Some`), so the collected `nbrs` is the identical set of unvisited
neighbour indices; after `sort` it is identical, so the same edges are pushed in the same order. Verified: A/B
**differential output-list parity** `assert_eq!(old, new)` (inline old-`neighbors`+`idx.get` vs new-
`neighbors_indices`, full BFS over 50000 nodes) passed before timing; the `test_generic_bfs_edges_depth` suite
test (depth-limited output) passes.

## Median A/B (paired-interleaved, one binary, NULL control)

`cargo test --release -p fnx-algorithms --lib generic_bfs_edges_idx_ab -- --ignored --nocapture`

BFS from node 0 over a 50000-node circulant (degree 20) — visits all nodes → 50000 output edges. 61 rounds.
Ratio = string/index, **>1 = index faster**.

| row | median | win_rate | p5_p95 |
|-----|-------:|---------:|--------|
| `INT_vs_string` | **2.4201x** | 61/61 | [1.9674, 2.7280] |
| `NULL_int_vs_int` | 1.0069x | 34/61 | [0.8847, 1.1047] |

Decisive: candidate p5 (1.97) ~1.8x above the NULL p95 (1.10); all 61 rounds won.

## Clippy note

My change is clippy-clean (0 findings in production ~41760-41772 / test ~71599-71723, grep-verified). The
crate has 12 pre-existing clippy `-D warnings` errors in peer/committed code — left untouched per
shared-checkout discipline.

## Files

- Production: `crates/fnx-algorithms/src/lib.rs` — `generic_bfs_edges`.
- Test-only: `generic_bfs_edges_idx_ab` A/B.

## Vein status

Ninth "name-keyed → integer" sub-family win. Notable: an **ordered-output** traversal that is still safe to
convert because it `sort`s its neighbour frontier (the sort canonicalises the order). Lesson for the sweep:
an ordered output is only a blocker if the order depends on the *unsorted* neighbour-iteration order — a
`sort()` before emit makes it order-safe.
