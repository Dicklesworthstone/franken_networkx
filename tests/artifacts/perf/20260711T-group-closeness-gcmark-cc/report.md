# br-r37-c1-gcmark — `group_closeness_centrality` integer-adjacency multi-source BFS

Status: **SHIP.** 7.17x median self-speedup, bit-identical.

## The target

`group_closeness_centrality(graph, group)` = `non_group_count / Σ dist(group→v)` via
one multi-source BFS from the group. The old kernel walked
`graph.neighbors(nodes[v])` (a fresh `Vec<&str>` alloc per pop) and re-hashed each
neighbour name through `idx` to recover its integer index.

## The lever

Walk `graph.neighbors_indices(v)` (zero-alloc `&[usize]`) directly in the BFS;
`idx.get` never rejected a neighbour, so every neighbour index is visited as
before. `idx` is retained only to seed the group node indices, and
`group_set`/`nodes` for the final non-group filter (both cheap / off the hot path).

## Bit-identical argument

`neighbors_indices(v)` yields the same neighbour set in the same adjacency order as
`neighbors(nodes[v])`, so the BFS distances are identical; `total_dist` is the same
exact integer sum, and the result `non_group_count / total_dist` is a single
division over the same integers. Verified in-test with an exact `to_bits()`
comparison against the String baseline (`group_closeness_centrality_orig_string`,
`#[cfg(test)]`); the existing `test_group_closeness_centrality_hub` unit test is
green.

## Median A/B (paired-interleaved, one binary, NULL control)

`cargo test --release -p fnx-algorithms --lib group_closeness_gcmark_ab -- --ignored --nocapture`

Pseudo-random graph n=1500 deg~10, group of 3 spread-out nodes, 61→121 rounds.
Ratio = base/cand, **>1 means integer-BFS faster**.

| row | median | win_rate | p5_p95 |
|-----|-------:|---------:|--------|
| `INT_vs_string` | **7.1686x** | 121/121 | [5.4649, 9.7570] |
| `NULL_int_vs_int` | 0.9976x | 59/121 | [0.7218, 1.4180] |

The lever median (7.17x) clears the NULL floor: candidate p5 (5.46) is ~4x above
the NULL p95 (1.42), and every one of 121 paired rounds won.

## Gates

- A/B `cargo test --release` build: compiled + ran clean.
- `to_bits()` parity + `test_group_closeness_centrality_hub`: green.
- clippy `-D warnings`: clean (after retrying past the fleet-wide `ftui` path-dep
  flake).
- pyo3 `group_closeness_centrality` calls this kernel directly — the win reaches
  Python.

## Files

- Production: `crates/fnx-algorithms/src/lib.rs` — `group_closeness_centrality`.
- Test-only: `group_closeness_centrality_orig_string` baseline + `..._gcmark_ab` A/B.
