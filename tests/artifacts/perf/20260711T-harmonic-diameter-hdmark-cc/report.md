# br-r37-c1-hdmark — `harmonic_diameter` integer-adjacency all-pairs BFS

Status: **SHIP.** 10.95x median self-speedup, bit-identical.

## The target

`harmonic_diameter(graph)` = `n_pairs / Σ_{s<t} 1/d(s,t)` — an all-pairs BFS
(O(V·(V+E))). The old kernel walked `graph.neighbors(nodes[v])` (a fresh `Vec<&str>`
allocation per pop) and re-hashed each neighbour name through `idx` to recover its
integer index:

```rust
for s in 0..n {
    let mut dist = vec![usize::MAX; n];
    ...
    while let Some(v) = queue.pop_front() {
        if let Some(nbrs) = graph.neighbors(nodes[v]) {          // Vec<&str> alloc / pop
            for nb in nbrs {
                if let Some(&ni) = idx.get(nb) && dist[ni] == usize::MAX {   // String hash
                    ...
                }
            }
        }
    }
    for t in (s+1)..n { if dist[t] < MAX && dist[t] > 0 { reciprocal_sum += 1.0/dist[t] as f64 } }
}
```

## The lever

Walk `graph.neighbors_indices(v)` (zero-alloc `&[usize]`) directly; `idx.get`
never rejected a neighbour, so every neighbour index is visited as before. The
`idx` HashMap and the `nodes` vector are dropped entirely.

## Bit-identical argument

The BFS distances are order-independent shortest paths (`neighbors_indices`
preserves the adjacency order anyway), so the `dist` array is identical. Crucially,
`reciprocal_sum` accumulates `1.0/dist[t] as f64` in the SAME fixed order — outer
`s` ascending, inner `t` ascending, NOT HashMap order — over the SAME integer
distances. The sequence of float additions is therefore unchanged, so
`reciprocal_sum`, `n_pairs / reciprocal_sum`, and the result are **bit-identical**.
Verified in-test with an exact `to_bits()` comparison against the String baseline
(`harmonic_diameter_orig_string`, `#[cfg(test)]`); the existing
`test_harmonic_diameter_path` unit test is green.

## Median A/B (paired-interleaved, one binary, NULL control)

`cargo test --release -p fnx-algorithms --lib harmonic_diameter_hdmark_ab -- --ignored --nocapture`

Well-connected graph (spanning path + random edges to ~deg-10), n=200. fnx candidate
(integer BFS) vs the preserved String baseline, interleaved in one process, 61
rounds. Ratio = base/cand, **>1 means integer-BFS faster**.

| row | median | win_rate | p5_p95 |
|-----|-------:|---------:|--------|
| `INT_vs_string` | **10.9465x** | 61/61 | [9.0053, 13.3057] |
| `NULL_int_vs_int` | 1.0014x | 31/61 | [0.8839, 1.1215] |

The lever median (10.95x) clears the NULL floor: candidate p5 (9.01) is ~8x above
the NULL p95 (1.12), and every one of 61 paired rounds won.

## Gates

- A/B `cargo test --release` build (compiles the test target): exit 0.
- `to_bits()` parity + `test_harmonic_diameter_path`: green.
- clippy `-D warnings`: clean (after retrying past a transient per-worker `ftui`
  path-dep resolution flake unrelated to this change).
- pyo3 `harmonic_diameter` calls this kernel directly — the win reaches Python.

## Files

- Production: `crates/fnx-algorithms/src/lib.rs` — `harmonic_diameter`.
- Test-only: `harmonic_diameter_orig_string` baseline + `..._hdmark_ab` A/B.
