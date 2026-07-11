# br-r37-c1-mismark — `maximum_independent_set` integer-adjacency + mark-array

Status: **SHIP.** 28.19x median self-speedup, byte-identical.

## The target

`maximum_independent_set(graph)` is a greedy min-effective-degree independent set —
O(V²·deg). The old kernel kept `remaining` as a `HashSet<String>` and, on EVERY
while iteration, recomputed each remaining node's effective degree via
`graph.neighbors(a)` (a fresh `Vec<&str>` alloc) + `remaining.contains(...)` String
probes, inside a `min_by` over the HashSet:

```rust
let mut remaining: HashSet<String> = nodes.iter().map(|s| s.to_string()).collect();
while !remaining.is_empty() {
    let min_node = remaining.iter().min_by(|&a, &b| {
        let deg_a = graph.neighbors(a).map(|nbrs| nbrs.iter().filter(|&n| remaining.contains(*n)).count())...;
        let deg_b = graph.neighbors(b)...;
        deg_a.cmp(&deg_b).then_with(|| a.cmp(b))          // total order on (deg, name)
    }).unwrap().clone();
    ...
}
```

## The lever

Mark `remaining` in a `bool` array indexed by node index, scan remaining indices
`0..n`, and compute each node's effective degree once by walking
`graph.neighbors_indices(a)` with O(1) `in_remaining[ni]` probes. The
`HashSet<String>`, the per-node `Vec<&str>` allocation, and the `remaining.contains`
String hashing are all removed.

## Byte-identical argument

The selection key `(effective_degree, node name)` is a TOTAL order — node names are
unique, so no two nodes are equal under it. The old `min_by` therefore returned THE
unique minimum regardless of `HashSet` iteration order; scanning indices `0..n` and
keeping the strict `(deg, name)`-minimum picks the same unique winner. Effective
degree is the same integer count; the name tie-break compares the same node names;
the removed-neighbour set and the final `sort()`ed output are unchanged. Verified
in-test: the integer result is `assert_eq!`-equal to the String baseline
(`maximum_independent_set_orig_string`, `#[cfg(test)]`), and the existing
`test_maximum_independent_set_{triangle,path,empty}` unit tests are green.

## Median A/B (paired-interleaved, one binary, NULL control)

`cargo test --release -p fnx-algorithms --lib maximum_independent_set_mismark_ab -- --ignored --nocapture`

Pseudo-random graph n=500 deg~6, 61 rounds. Ratio = base/cand, **>1 means the
mark-array kernel is faster**.

| row | median | win_rate | p5_p95 |
|-----|-------:|---------:|--------|
| `MARK_vs_string` | **28.1929x** | 61/61 | [20.7313, 59.4518] |
| `NULL_mark_vs_mark` | 1.0038x | 32/61 | [0.9207, 1.0846] |

The lever median (28.19x) dwarfs the NULL floor: candidate p5 (20.73) is ~19x above
the NULL p95 (1.08), and every one of 61 paired rounds won. The per-iteration
`HashSet<String>` rebuild-free scan + zero-alloc integer degree computation removes
the O(V²·deg) String tax.

## Gates

- A/B `cargo test --release` build compiled + ran clean; 3 unit tests + parity
  assert green.
- clippy `-D warnings`: clean (after retrying past the fleet-wide `ftui` path-dep flake).
- pyo3 `maximum_independent_set` calls this kernel directly — the win reaches Python.

## Files

- Production: `crates/fnx-algorithms/src/lib.rs` — `maximum_independent_set`.
- Test-only: `maximum_independent_set_orig_string` baseline + `..._mismark_ab` A/B.
