# br-r37-c1-hwidx — `hyper_wiener_index` integer-adjacency all-pairs BFS

Status: **SHIP.** 12.46x median self-speedup, bit-identical. clippy clean.

## The target

`hyper_wiener_index(graph)` = `Σ_{s<t} (d(s,t) + d(s,t)²)` — an all-pairs BFS
distance metric (O(V·(V+E))), the last member of the distance-metric family
(`gutman_index`, `schultz_index`, this). The old kernel walked
`graph.neighbors(nodes[v])` (a `Vec<&str>` alloc per pop) + `idx.get(nb)` String hash
in the BFS.

## The lever

Walk `graph.neighbors_indices(v)` directly (zero-alloc `&[usize]`); `idx` and `nodes`
dropped. No degree computation (unlike gutman/schultz) — just distances, so the
per-pair sum `total += d + d*d` (`d = dist[t] as f64`) is unchanged.

## Bit-identical argument

BFS distances are order-independent shortest paths, and `total` accumulates
`d + d*d` in the SAME fixed (s ascending, then t ascending) order over the same
integer distances — the exact same float-op sequence. The disconnection
short-circuit (`dist.contains(&MAX)` → `None`) is preserved. Verified in-test with an
exact `to_bits()` comparison against the String baseline
(`hyper_wiener_index_orig_string`, `#[cfg(test)]`); the existing
`test_hyper_wiener_index_{path,path_four_nodes}` unit tests are green.

## Median A/B (paired-interleaved, one binary, NULL control)

`cargo test --release -p fnx-algorithms --lib hyper_wiener_index_hwidx_ab -- --ignored --nocapture`

Connected graph n=200 deg~10, 61 rounds. Ratio = base/cand, **>1 means integer-BFS
faster**.

| row | median | win_rate | p5_p95 |
|-----|-------:|---------:|--------|
| `INT_vs_string` | **12.4613x** | 61/61 | [10.6301, 17.0721] |
| `NULL_int_vs_int` | 1.0111x | 34/61 | [0.8485, 1.2431] |

The lever median (12.46x) clears the NULL floor: candidate p5 (10.63) is ~8.5x above
the NULL p95 (1.24), and every one of 61 paired rounds won.

## Family complete

`gutman_index` (13.21x), `schultz_index` (12.15x), `hyper_wiener_index` (12.46x) —
the distance-metric-index family is fully converted to integer-adjacency all-pairs
BFS.

## Gates

- clippy `-D warnings`: clean (attempt 1).
- A/B `cargo test --release` ran clean; `to_bits()` parity + 2 unit tests green.
- pyo3 `hyper_wiener_index` calls this kernel directly — the win reaches Python.

## Files

- Production: `crates/fnx-algorithms/src/lib.rs` — `hyper_wiener_index`.
- Test-only: `hyper_wiener_index_orig_string` baseline + `..._hwidx_ab` A/B.
