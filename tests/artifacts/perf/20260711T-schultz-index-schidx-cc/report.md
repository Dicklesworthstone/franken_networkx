# br-r37-c1-schidx — `schultz_index` integer-adjacency all-pairs BFS

Status: **SHIP.** 12.15x median self-speedup, bit-identical. clippy clean.

## The target

`schultz_index(graph)` = `Σ_{s<t} (deg(s)+deg(t))·d(s,t)` — an all-pairs BFS
distance metric (O(V·(V+E))), the additive twin of `gutman_index`. The old kernel
walked `graph.neighbors(nodes[v])` (a `Vec<&str>` alloc per pop) + `idx.get(nb)` in
the BFS, and used `graph.neighbors(nodes[s]).len()` (a `Vec<&str>` alloc just to
count) per degree.

## The lever

Identical to `gutman_index` (br-r37-c1-gutidx): walk `graph.neighbors_indices(v)`
directly (zero-alloc `&[usize]`), take degrees with
`neighbors_indices(s).map_or(0, <[usize]>::len)`; `idx` and `nodes` dropped. Only the
accumulator differs: `((du + dv) * dist[t])` vs gutman's `(du * dv * dist[t])`.

## Bit-identical argument

BFS distances are order-independent shortest paths, degrees are the same neighbour
counts, and `total` sums `((du + dv) * dist[t]) as f64` in the SAME fixed (s asc, t
asc) order over the same integers — the exact same float-op sequence. Disconnection
short-circuit preserved. Verified in-test with an exact `to_bits()` comparison against
the String baseline (`schultz_index_orig_string`, `#[cfg(test)]`);
`test_schultz_index_path` green.

## Median A/B (paired-interleaved, one binary, NULL control)

`cargo test --release -p fnx-algorithms --lib schultz_index_schidx_ab -- --ignored --nocapture`

Connected graph n=200 deg~10, 61 rounds. Ratio = base/cand, **>1 means integer-BFS
faster**.

| row | median | win_rate | p5_p95 |
|-----|-------:|---------:|--------|
| `INT_vs_string` | **12.1541x** | 61/61 | [10.3260, 13.2613] |
| `NULL_int_vs_int` | 0.9993x | 27/61 | [0.9780, 1.0532] |

The lever median (12.15x) clears the NULL floor: candidate p5 (10.33) is ~10x above
the NULL p95 (1.05), and every one of 61 paired rounds won.

## Gates

- clippy `-D warnings`: **clean** (one batch pass over the working tree — which also
  retroactively cleared the ftui-blocked gcmark/mismark/gutidx clippy debt).
- A/B `cargo test --release` ran clean; `to_bits()` parity + `test_schultz_index_path` green.
- pyo3 `schultz_index` calls this kernel directly — the win reaches Python.

## Files

- Production: `crates/fnx-algorithms/src/lib.rs` — `schultz_index`.
- Test-only: `schultz_index_orig_string` baseline + `..._schidx_ab` A/B.
