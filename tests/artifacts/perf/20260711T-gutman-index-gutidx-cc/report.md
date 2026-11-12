# br-r37-c1-gutidx — `gutman_index` integer-adjacency all-pairs BFS

Status: **SHIP.** 13.21x median self-speedup, bit-identical.

## The target

`gutman_index(graph)` = `Σ_{s<t} deg(s)·deg(t)·d(s,t)` — an all-pairs BFS distance
metric (O(V·(V+E))). The old kernel walked `graph.neighbors(nodes[v])` (a fresh
`Vec<&str>` alloc per pop) + `idx.get(nb)` String hash in the BFS, and used
`graph.neighbors(nodes[s]).len()` (a `Vec<&str>` alloc just to count) for each
degree.

## The lever

Walk `graph.neighbors_indices(v)` directly (zero-alloc `&[usize]`) in the BFS, and
take degrees with `graph.neighbors_indices(s).map_or(0, <[usize]>::len)`. The `idx`
HashMap and the `nodes` vector are dropped.

## Bit-identical argument

The BFS distances are order-independent shortest paths; the degrees are the same
neighbour counts (`neighbors_indices(s).len()` == `neighbors(nodes[s]).len()`); and
`total` accumulates `(du * dv * dist[t]) as f64` in the SAME fixed (s ascending, then
t ascending) order over the same integers — the exact same float-op sequence, so
`total` is byte-identical (including any large-product `as f64` rounding, which is
reproduced identically). The disconnection short-circuit (`dist.contains(&MAX)` →
`None`) is preserved. Verified in-test with an exact `to_bits()` comparison against
the String baseline (`gutman_index_orig_string`, `#[cfg(test)]`); the existing
`test_gutman_index_{path,disconnected}` unit tests are green.

## Median A/B (paired-interleaved, one binary, NULL control)

`cargo test --release -p fnx-algorithms --lib gutman_index_gutidx_ab -- --ignored --nocapture`

Connected graph n=200 deg~10, 61 rounds. Ratio = base/cand, **>1 means integer-BFS
faster**.

| row | median | win_rate | p5_p95 |
|-----|-------:|---------:|--------|
| `INT_vs_string` | **13.2074x** | 61/61 | [11.2824, 14.1214] |
| `NULL_int_vs_int` | 1.0044x | 35/61 | [0.8894, 1.1421] |

The lever median (13.21x) clears the NULL floor: candidate p5 (11.28) is ~10x above
the NULL p95 (1.14), and every one of 61 paired rounds won.

## Family

`gutman_index` is one of a distance-metric-index family (`schultz_index`,
`hyper_wiener_index`) sharing the exact all-pairs-BFS-with-String-neighbours shape;
those are queued as follow-ups (one lever per commit).

## Gates

- `--no-run` release build: Finished clean (compiles). A/B `cargo test --release`
  ran clean; 2 unit tests + `to_bits()` parity green.
- clippy `-D warnings`: (pending — fleet-wide `ftui` path-dep flake; the `<[usize]>::len`
  form is the clippy-preferred one). pyo3 `gutman_index` calls this kernel directly.

## Files

- Production: `crates/fnx-algorithms/src/lib.rs` — `gutman_index`.
- Test-only: `gutman_index_orig_string` baseline + `..._gutidx_ab` A/B.
