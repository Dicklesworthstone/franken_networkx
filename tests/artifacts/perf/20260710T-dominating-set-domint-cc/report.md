# br-r37-c1-domint — `dominating_set` integer-adjacency + mark-array greedy

Status: **SHIP.** 20.13x median self-speedup, byte-identical.

## The target

`dominating_set(graph)` is an O(V·E) greedy max-cover: while any node is
undominated, rescan every undominated node, count how many undominated nodes it
would cover (self + undominated neighbours), and pick the best. The old kernel
kept the dominated set as a `HashSet<&str>` and, on **every pass**, called
`graph.neighbors(node)` (a fresh `Vec<&str>` allocation) for each undominated node
and probed `dominated.contains(nbr)` with String hashing:

```rust
let mut dominated: HashSet<&str> = HashSet::new();
while dominated.len() < nodes.len() {
    for &node in &nodes {
        if dominated.contains(node) { continue; }
        let mut cover = 1;
        if let Some(nbrs) = graph.neighbors(node) {          // Vec<&str> alloc / node / pass
            for nbr in &nbrs {
                if !dominated.contains(nbr) { cover += 1; }  // String hash-probe
            }
        }
        ...
    }
    ...
}
```

Over the whole run that is O(V·E) String allocations + hashes — the greedy runs
~V/deg passes and each pass re-materialises the undominated frontier's adjacency.

## The lever

- `dominated: Vec<bool>` mark array indexed by node index (O(1) probe) instead of
  `HashSet<&str>`;
- `dominated_count` mirrors the old `HashSet::len()` (incremented only on a
  `false → true` flip, i.e. distinct marked indices);
- walk `graph.neighbors_indices(node)` (zero-alloc `&[usize]`) instead of
  `graph.neighbors(node)`.

## Byte-identical argument

`cover` (self + count of undominated neighbours) is the same integer under either
representation. The greedy pick is the FIRST node in `nodes_ordered()` order that
attains the strict-max cover (`cover > best_cover`), and index iteration `0..n`
walks that exact order. The dominated set grows by the same node (the pick) plus
the same neighbour set each pass, so `dominated_count` tracks `HashSet::len()`
exactly and the selection sequence is identical. Output is a `Vec<String>` sorted
`sort_unstable()` — no floats anywhere. Verified in-test: the integer selection is
`assert_eq!`-equal to the String baseline (`dominating_set_orig_string`, kept
`#[cfg(test)]`); the test would panic on any mismatch and passed.

## Median A/B (paired-interleaved, one binary, NULL control)

`cargo test --release -p fnx-algorithms --lib dominating_set_domint_ab -- --ignored --nocapture`

Moderate-degree pseudo-random graph, n=1500, deg=10 (many greedy passes). fnx
candidate (mark-array) vs the preserved String-HashSet baseline, interleaved in one
process, 121 rounds. Ratio = base/cand, so **>1 means the mark-array kernel is
faster**.

| row | median | win_rate | p5_p95 |
|-----|-------:|---------:|--------|
| `MARK_vs_string` | **20.1345x** | 121/121 | [19.1448, 21.3703] |
| `NULL_mark_vs_mark` | 1.0022x | 73/121 | [0.9842, 1.0390] |

The lever median (20.13x) clears the NULL floor decisively: candidate p5 (19.14) is
~18x above the NULL p95 (1.04), CI is tight, and every one of 121 paired rounds won.

## Gates

- `cargo check -p fnx-algorithms --all-targets` (remote): exit 0, clean.
- clippy `-D warnings` (remote): clean.
- Existing `dominating_set` / `is_dominating_set` unit tests: green.

## Files

- Production: `crates/fnx-algorithms/src/lib.rs` — `dominating_set`.
- Test-only: `dominating_set_orig_string` baseline + `dominating_set_domint_ab` A/B.
