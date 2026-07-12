# br-r37-c1-lrcidx — local_reaching_centrality integer-index BFS

Status: **SHIP.** 21.47x, ULP-identical. Opens a fresh sub-family (reached String-`HashSet` BFS that looks
"done" but still hashes names). My change clippy-clean (crate has pre-existing peer lint debt, untouched).

## The target

`local_reaching_centrality(graph, node)` (fnx-algorithms) — BFS the set of nodes reachable from `node` and
return `reachable / (n-1)`. It is called directly (reached) **and** once per node by
`global_reaching_centrality` (n calls → `O(n·(V+E))`). The BFS used a `HashSet<&str> visited` — a **String
hash per visited node** — even though it already iterated via `neighbors_iter` (no Vec alloc), which is why
the String→index sweep skipped it.

## The lever

Resolve the start node once (`get_node_index`), then BFS over `graph.neighbors_indices` (zero-alloc
`&[usize]`) with a `vec![false; n]` visited-mark, counting reached nodes directly. Drops the per-node String
hashing across the whole sweep.

## Byte-identical argument

BFS reachability is order-independent — the set of reached nodes (hence `reachable = count - 1`) is identical
regardless of neighbour-visit order or key type. `neighbors_indices(i)` yields the same neighbours as
`neighbors_iter` (just as indices), and `get_node_index(node)` is `Some` because `has_node(node)` is checked
above. The returned ratio `reachable / (n-1)` is a single `f64`, bit-identical. Verified: A/B parity
`assert_eq!(old.to_bits(), new.to_bits())` (exact f64 bits, driven through the `global_reaching_centrality`
loop) passed before timing; the 5 reaching-centrality suite tests pass, including
`test_local_reaching_centrality_disconnected` (partial reachability).

## Median A/B (paired-interleaved, one binary, NULL control)

`cargo test --release -p fnx-algorithms --lib local_reaching_centrality_idx_ab -- --ignored --nocapture`

`global_reaching_centrality` (= n local calls) on a 1000-node connected circulant (degree 20). 61 rounds.
Ratio = string/index, **>1 = index faster**.

| row | median | win_rate | p5_p95 |
|-----|-------:|---------:|--------|
| `IDX_vs_string` | **21.4735x** | 61/61 | [17.5836, 25.3173] |
| `NULL_idx_vs_idx` | 0.9961x | 29/61 | [0.8372, 1.2092] |

Decisive: candidate p5 (17.58) ~14.5x above the NULL p95 (1.21); all 61 rounds won. The `HashSet<&str>` String
hashing dominated the BFS; dropping it is a >20x win on the O(n·(V+E)) sweep.

## Clippy note

My change is clippy-clean (0 findings in production ~31595-31624 / test ~70376-70516, grep-verified). The
crate has 12 pre-existing clippy `-D warnings` errors in peer/committed code — left untouched per
shared-checkout discipline.

## Files

- Production: `crates/fnx-algorithms/src/lib.rs` — `local_reaching_centrality`.
- Test-only: `local_reaching_centrality_idx_ab` A/B.

## Vein status

Opens the **"neighbors_iter + HashSet<&str>" residual** sub-family: functions the String→index sweep skipped
because they already avoid the `neighbors()` Vec alloc, but still key the visited/dist structure by node
NAME. Next: sweep other reached, deterministic BFS/DFS fns with `HashSet<&str>`/`HashMap<&str, _>` over
`neighbors_iter` (e.g. `local_reaching_centrality_directed`, and the `dominating_set`/`edge_boundary` family).
