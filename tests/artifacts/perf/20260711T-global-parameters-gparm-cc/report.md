# br-r37-c1-gparm — `global_parameters` integer-adjacency all-pairs BFS + count pass

Status: **SHIP.** 19.86x median self-speedup, byte-identical.

## The target

`global_parameters(graph)` computes the intersection array `(b_k, c_k)` of a
distance-regular graph: an all-pairs BFS, then an O(V²·diameter) pass that, for each
pair `(i, j)` at distance `k`, counts `j`'s neighbours at distance `k±1` from `i`.
The old kernel walked `graph.neighbors(nodes[v])` (a `Vec<&str>` alloc per BFS pop)
+ `idx.get(nb)`, AND `graph.neighbors(nodes[j])` + `idx.get(nb)` once per (i,j) pair
— O(V²) `Vec<&str>` allocations and O(V²·deg) `idx.get` String hashes.

## The lever

Walk `graph.neighbors_indices(v)` / `graph.neighbors_indices(j)` directly (zero-alloc
`&[usize]`); `idx` and `nodes` dropped. `idx.get` never rejected a neighbour, so
every neighbour index is counted as before.

## Byte-identical argument

The BFS distances are order-independent shortest paths; `b_count`/`c_count` are the
same integer counts; and the `b_vals`/`c_vals` HashSets have the same contents, so
`.len()` (distinct values) is unchanged — the distance-regularity `None`
short-circuit and the single extracted value are identical. Output is
`Option<(Vec<usize>, Vec<usize>)>` — integers, no float. Verified in-test across the
Some path (K₁₁₀ complete + C₂₀ cycle, both distance-regular → `Some`) and the None
path (a 20-node path, not distance-regular → `None`): all three
`assert_eq!(global_parameters, baseline)`.

## Median A/B (paired-interleaved, one binary, NULL control)

`cargo test --release -p fnx-algorithms --lib global_parameters_gparm_ab -- --ignored --nocapture`

Complete graph K₁₁₀ (distance-regular → runs the full count pass, each node's whole
neighbour list allocated + hashed in the baseline). 61 rounds. Ratio = base/cand,
**>1 means integer faster**.

| row | median | win_rate | p5_p95 |
|-----|-------:|---------:|--------|
| `INT_vs_string` | **19.8644x** | 61/61 | [15.7362, 33.0569] |
| `NULL_int_vs_int` | 0.9965x | 28/61 | [0.8750, 1.1275] |

The lever median (19.86x) dwarfs the NULL floor: candidate p5 (15.74) is ~14x above
the NULL p95 (1.13), and every one of 61 paired rounds won.

## Gates

- clippy `-D warnings`: clean.
- A/B `cargo test --release` ran clean; parity across K/cycle/path (Some+None) green.
- pyo3 `global_parameters` calls this kernel directly — the win reaches Python.

## Files

- Production: `crates/fnx-algorithms/src/lib.rs` — `global_parameters`.
- Test-only: `global_parameters_orig_string` baseline + `..._gparm_ab` A/B.
