# br-r37-c1-clvit — `closeness_vitality` full-index integer BFS

Status: **SHIP.** 10.70x median self-speedup, byte-identical.

## The target

`closeness_vitality(graph)` — O(V²·E) — computes, for each node, the change in the
graph's Wiener index (sum of shortest-path distances) when that node is removed.
For every excluded node it BFSes from every remaining node in the induced
subgraph. The old kernel, per excluded node, rebuilt a `HashMap<&str, usize>`
(`node_to_idx` over the remaining nodes) and, per BFS pop, called
`graph.neighbors(remaining_nodes[u])` (a fresh `Vec<&str>` allocation) then
re-hashed every neighbour name through `node_to_idx`:

```rust
for excluded_node in &nodes {
    let node_to_idx: HashMap<&str, usize> = ...;             // rebuilt per excluded node
    for s in 0..subgraph_n {
        let mut dist = vec![None; subgraph_n];
        ...
        while let Some(u) = queue.pop_front() {
            if let Some(nbrs) = graph.neighbors(remaining_nodes[u]) {   // Vec<&str> alloc / pop
                for nbr in nbrs {
                    if nbr == *excluded_node { continue; }
                    if let Some(&v) = node_to_idx.get(nbr) { ... }       // String hash-probe
                }
            }
        }
    }
}
```

Over a full call that is O(V³·d) String allocations + hashes.

## The lever

Snapshot integer adjacency ONCE (`adj: Vec<&[usize]>`, zero-copy borrows of the
graph's adjacency slices) and run every subgraph BFS in the FULL node-index space,
marking the excluded index `ex` and skipping it. `node_to_idx` is eliminated
entirely.

## Byte-identical argument

- `remaining_nodes` preserves `nodes_ordered()` order, so full-index order agrees
  with subgraph-index order → the pair enumeration `v > s` is preserved.
- Every neighbour except `ex` is a remaining node, so the old
  `node_to_idx.get(nbr)` never rejected a non-excluded neighbour; the full-index
  `if v == ex { continue }` reproduces exactly the excluded-node skip.
- The BFS queue discipline (`VecDeque`, push_back/pop_front) and the adjacency
  order (`neighbors_indices` yields the same order as `neighbors`) are unchanged,
  so traversal order — and thus `edges_scanned` / `nodes_touched` — is identical.
- `subgraph_wiener` is a sum of integer BFS distances (each `< 2^53`, exact), so it
  is order-independent AND identical; `full_wiener - subgraph_wiener` is exact
  integer arithmetic. Disconnection detection (first unreachable pair →
  `f64::NEG_INFINITY`) is preserved and the result is order-invariant either way.

Verified in-test: `closeness_vitality(&g).vitality` is `assert_eq!`-equal to the
String baseline (`closeness_vitality_orig_string`, kept `#[cfg(test)]`) on the
n=150 connected graph; the test would panic on any mismatch and passed.

## Median A/B (paired-interleaved, one binary, NULL control)

`cargo test --release -p fnx-algorithms --lib closeness_vitality_clvit_ab -- --ignored --nocapture`

Well-connected graph (spanning path + random edges to ~deg-10), n=150 — most
single-node removals stay connected and do full work. fnx candidate (integer BFS)
vs the preserved String baseline, interleaved in one process, 61 rounds. Ratio =
base/cand, so **>1 means the integer-BFS kernel is faster**.

| row | median | win_rate | p5_p95 |
|-----|-------:|---------:|--------|
| `INT_vs_string` | **10.7008x** | 61/61 | [9.1749, 13.5913] |
| `NULL_int_vs_int` | 0.9981x | 25/61 | [0.8846, 1.1357] |

The lever median (10.70x) clears the NULL floor decisively: candidate p5 (9.17) is
~8x above the NULL p95 (1.14), and every one of 61 paired rounds won.

## Scope

Only `closeness_vitality` (the O(V²·E) heavy hitter) is converted here.
`closeness_vitality_single` (single excluded node, O(V·E), same shape) is left for
a trivial follow-up — the full function does not call it, so behaviour is
consistent.

## Gates

- `cargo check -p fnx-algorithms --all-targets` (remote): exit 0, clean.
- clippy `-D warnings` (remote): clean.
- Existing `closeness_vitality` unit tests (C3 cycle, bridge-node disconnection,
  empty): green.

## Files

- Production: `crates/fnx-algorithms/src/lib.rs` — `closeness_vitality`.
- Test-only: `closeness_vitality_orig_string` baseline + `closeness_vitality_clvit_ab` A/B.
