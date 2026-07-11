# br-r37-c1-srmark — `is_strongly_regular` integer-adjacency + mark-array

Status: **SHIP.** 75.30x median self-speedup — biggest of the session — byte-identical.

## The target

`is_strongly_regular(graph)` checks whether every vertex has the same degree,
every adjacent pair the same λ common neighbours, and every non-adjacent pair the
same μ common neighbours. The λ/μ scan rebuilt a `HashSet<&str>` for `j_nbrs` on
**every (i, j) pair** — O(V²) String-set allocations — and String-hash-intersected
it with `i_nbrs`:

```rust
for i in 0..n {
    let i_nbrs: HashSet<&str> = graph.neighbors(nodes[i])...collect();
    for j in (i+1)..n {
        let j_nbrs: HashSet<&str> = graph.neighbors(nodes[j])...collect();  // per PAIR
        let common = i_nbrs.intersection(&j_nbrs).count();                   // String hashing
        if i_nbrs.contains(nodes[j]) { ... } else { ... }
    }
}
```

## The lever

Snapshot integer adjacency ONCE (`Vec<&[usize]>`), mark N(i) in a reusable `bool`
array per `i`, and count `|N(i) ∩ N(j)|` by walking `adj[j]` with O(1) probes; the
adjacency test `j ∈ N(i)` becomes `in_i[j]`. The per-pair `HashSet<&str>` build is
gone.

## Byte-identical argument

`common` is the same integer intersection size (a simple `Graph` has distinct
neighbours, so the HashSet dedupe was a no-op). The pair-iteration order (i, then
j > i) is unchanged, so the first λ/μ assignment and any early `false` return fire
on the same pair; and the boolean result is order-independent regardless (it holds
iff all adjacent pairs share one constant and all non-adjacent pairs share
another). Verified in-test across the true path and both false paths:

- K₁₁₀ (complete → strongly regular (n, n-1, n-2, 0), returns **true**, full scan),
- a 40-node path (non-regular → early **false**),
- C₄₀ cycle (regular but not strongly regular → **false** mid-scan).

All three `assert_eq!(is_strongly_regular, baseline)`; the test passed.

## Median A/B (paired-interleaved, one binary, NULL control)

`cargo test --release -p fnx-algorithms --lib is_strongly_regular_srmark_ab -- --ignored --nocapture`

Complete graph K₁₁₀ (exercises the full O(V²·deg) scan). fnx candidate (mark-array)
vs the preserved String baseline, interleaved in one process, 61 rounds. Ratio =
base/cand, so **>1 means the mark-array kernel is faster**.

| row | median | win_rate | p5_p95 |
|-----|-------:|---------:|--------|
| `MARK_vs_string` | **75.2999x** | 61/61 | [55.4510, 109.0383] |
| `NULL_mark_vs_mark` | 0.9880x | 24/61 | [0.5408, 1.8218] |

The lever median (75.30x) dwarfs the NULL floor: candidate p5 (55.45) is ~30x above
the NULL p95 (1.82), and every one of 61 paired rounds won. (The NULL spread is
wide because K₁₁₀'s dense O(V²·deg) call has high per-round timing variance, but the
signal is orders of magnitude above that noise.) The per-pair `HashSet<&str>` build
+ String intersection was the dominant cost on a dense regular graph.

## Gates

- `cargo check -p fnx-algorithms --all-targets` (remote): exit 0.
- clippy `-D warnings` (remote): clean.
- Parity asserts (K₁₁₀ / path / cycle): green.
- pyo3 `is_strongly_regular` calls this kernel directly — the win reaches Python.

## Files

- Production: `crates/fnx-algorithms/src/lib.rs` — `is_strongly_regular`.
- Test-only: `is_strongly_regular_orig_string` baseline + `..._srmark_ab` A/B.
