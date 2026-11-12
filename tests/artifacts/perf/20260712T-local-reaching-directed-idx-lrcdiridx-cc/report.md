# br-r37-c1-lrcdiridx — local_reaching_centrality_directed integer-index BFS

Status: **SHIP.** 18.75x, ULP-identical. DiGraph mirror of br-r37-c1-lrcidx. My change clippy-clean (crate
has pre-existing peer lint debt, untouched).

## The target

`local_reaching_centrality_directed(digraph, node)` (fnx-algorithms) — BFS the forward-reachable set from
`node`, return `reachable / (n-1)`. Reached directly and once per node by
`global_reaching_centrality_directed` (n calls → `O(n·(V+E))`). Its BFS used a `HashSet<&str> visited` (a
String hash per visited node) and, worse than the undirected sibling, `digraph.successors(current)` — a
`Vec<&str>` alloc per pop.

## The lever

Resolve the start node once (`get_node_index`), then BFS over `digraph.successors_indices` (zero-alloc
`&[usize]`) with a `vec![false; n]` visited-mark, counting reached nodes directly. Drops both the per-node
String hashing and the per-pop `Vec<&str>` allocation.

## Byte-identical argument

Forward reachability is order-independent — the reached set (hence `reachable = count - 1`) is identical
regardless of visit order or key type. `successors_indices(idx)` yields the same successors as the name-based
`successors()`, just as indices (the A/B ULP parity confirms this equivalence). `get_node_index(node)` is
`Some` because `has_node(node)` is checked. The ratio is a single `f64`, bit-identical. Verified: A/B parity
`assert_eq!(old.to_bits(), new.to_bits())` (exact f64 bits, through the `global_reaching_centrality_directed`
loop) passed before timing; the reaching-centrality suite tests pass, including
`test_local_reaching_centrality_directed_chain` and `test_global_reaching_centrality_directed_chain` (the
exact directed forward-reachability code path).

## Median A/B (paired-interleaved, one binary, NULL control)

`cargo test --release -p fnx-algorithms --lib local_reaching_centrality_directed_idx_ab -- --ignored --nocapture`

`global_reaching_centrality_directed` (= n local calls) on a 1000-node directed circulant (out-degree 10).
61 rounds. Ratio = string/index, **>1 = index faster**.

| row | median | win_rate | p5_p95 |
|-----|-------:|---------:|--------|
| `IDX_vs_string` | **18.7543x** | 61/61 | [14.9547, 25.7678] |
| `NULL_idx_vs_idx` | 0.9771x | 26/61 | [0.7275, 1.3155] |

Decisive: candidate p5 (14.95) ~11x above the NULL p95 (1.32); all 61 rounds won.

## Clippy note

My change is clippy-clean (0 findings in production ~31570-31600 / test ~70531-70670, grep-verified). The
crate has 12 pre-existing clippy `-D warnings` errors in peer/committed code — left untouched per
shared-checkout discipline.

## Files

- Production: `crates/fnx-algorithms/src/lib.rs` — `local_reaching_centrality_directed`.
- Test-only: `local_reaching_centrality_directed_idx_ab` A/B.

## Vein status

Second win in the "neighbors_iter/successors + HashSet<&str>" residual sub-family (after br-r37-c1-lrcidx).
The reaching-centrality pair (undirected + directed) is now fully integer-index. Next: sweep other reached,
deterministic BFS/DFS fns keyed by node name over the borrowed iterators (`dominating_set`, `edge_boundary`,
`tree_broadcast_center`).
