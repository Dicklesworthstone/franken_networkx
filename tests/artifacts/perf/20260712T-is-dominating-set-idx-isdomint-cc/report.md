# br-r37-c1-isdomint — is_dominating_set integer-index check

Status: **SHIP.** 6.09x, byte-identical (bool). Third win in the "neighbors + HashSet<&str>" residual
sub-family. My change clippy-clean (crate has pre-existing peer lint debt, untouched).

## The target

`is_dominating_set(graph, dom_nodes)` (fnx-algorithms) — returns whether every non-dominator node has a
dominator neighbour. The old kernel built a `HashSet<&str>` of `dom_nodes` and, per graph node, called
`graph.neighbors(node)` (a fresh `Vec<&str>` alloc) then probed the String set — a single O(V+E) pass with a
`Vec<&str>` alloc per node + String hashes.

## The lever

Mark dominators in a `vec![false; n]` by node index (`get_node_index`), then walk
`graph.neighbors_indices(node)` (zero-alloc `&[usize]`) with O(1) array probes.

## Byte-identical argument

The result is a `bool` and the check is a universal test ("every non-dom node has a dom neighbour"), so it is
order-independent; the pass iterates `0..n` = `nodes_ordered()` order, returning on the same first violation.
`dom_nodes` that are not in the graph were inert in the old `HashSet` (they never equalled a real node or
neighbour), so skipping them (`get_node_index → None`) changes nothing. `neighbors_indices(node)` yields the
same neighbours as `neighbors(node)`. Verified: A/B parity `assert_eq!(old_bool, new_bool)` passed before
timing; the suite tests `is_dominating_set_valid` (true path) and `is_dominating_set_invalid` (false path)
pass.

## Median A/B (paired-interleaved, one binary, NULL control)

`cargo test --release -p fnx-algorithms --lib is_dominating_set_idx_ab -- --ignored --nocapture`

50000-node circulant (degree 10) with a valid dominating set (every 11th node) so the pass scans all nodes.
61 rounds. Ratio = string/index, **>1 = index faster**.

| row | median | win_rate | p5_p95 |
|-----|-------:|---------:|--------|
| `IDX_vs_string` | **6.0885x** | 61/61 | [4.8616, 8.3250] |
| `NULL_idx_vs_idx` | 0.9774x | 21/61 | [0.7903, 1.1982] |

Decisive: candidate p5 (4.86) ~4x above the NULL p95 (1.20); all 61 rounds won. Smaller than the reaching-
centrality wins (21x/19x) because is_dominating_set is a single O(V+E) pass, not an n-call sweep — but the
per-node `Vec<&str>` alloc + String hash drop is a clean 6x.

## Clippy note

My change is clippy-clean (0 findings in production ~22666-22690 / test ~70684-70807, grep-verified). The
crate has 12 pre-existing clippy `-D warnings` errors in peer/committed code — left untouched per
shared-checkout discipline.

## Files

- Production: `crates/fnx-algorithms/src/lib.rs` — `is_dominating_set`.
- Test-only: `is_dominating_set_idx_ab` A/B.

## Vein status

Third win in the "neighbors/successors + HashSet<&str>" residual sub-family (after lrcidx 21.47x + lrcdiridx
18.75x). Note: `dominating_set` (br-r37-c1-domint), `edge_boundary`, `tree_broadcast_center` are already
integer. Next: continue the sweep for reached, deterministic name-keyed BFS/DFS/set-check fns.
