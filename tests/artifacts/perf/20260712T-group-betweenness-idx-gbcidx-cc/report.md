# br-r37-c1-gbcidx — group_betweenness_centrality n-source BFS integer swap

Status: **SHIP.** 5.67x, ULP-identical. Clean win (the n-source BFS is the dominant cost — no dilution). My
change clippy-clean (crate has pre-existing peer lint debt, untouched).

## The target

`group_betweenness_centrality(graph, group)` (fnx-algorithms) runs a BFS from **every** non-group source
(`for s in 0..n`, `O(n·(V+E))`) to count shortest-path multiplicities (`sigma`) and paths avoiding the group
(`sigma_no_c`), then accumulates `gbc_sum`. Each BFS iterated neighbours **by name**: `graph.neighbors(nodes
[v])` (a `Vec<&str>` alloc) + `idx.get(nb)` (a String re-hash per edge).

## The lever

Walk `graph.neighbors_indices(v)` (zero-alloc `&[usize]`) across the n-source BFS. The `idx` map is kept (used
to resolve the group names).

## Byte-identical (ULP) argument

`dist`, `sigma`, `sigma_no_c` are **order-independent integer** shortest-path quantities: `dist` is the BFS
distance (a graph property), and `sigma[ni] += sigma[v]` accumulates an integer sum over shortest-path
predecessors (integer addition is associative/commutative), so the final counts are identical regardless of
neighbour-iteration order. The result `gbc_sum` sums the integer ratios `paths_through_c / sigma[t]` in the
**fixed `t = 0..n` order** — no float reassociation depends on the BFS order. Every neighbour is a graph node
(old `idx.get` always `Some`). Hence the `f64` result is **bit-identical**. Verified: A/B parity `assert_eq!
(old.to_bits(), new.to_bits())` (exact f64 bits) passed before timing; `test_group_betweenness_centrality_
center` (validates the GBC value) passes.

## Median A/B (paired-interleaved, one binary, NULL control)

`cargo test --release -p fnx-algorithms --lib group_betweenness_idx_ab -- --ignored --nocapture`

1000-node circulant (degree 10), 3-node group → ~997 source BFS. 61 rounds. Ratio = string/index, **>1 =
index faster**.

| row | median | win_rate | p5_p95 |
|-----|-------:|---------:|--------|
| `INT_vs_string` | **5.6718x** | 61/61 | [4.2481, 6.9939] |
| `NULL_int_vs_int` | 1.0112x | 34/61 | [0.8471, 1.1845] |

Decisive: candidate p5 (4.25) ~3.6x above the NULL p95 (1.18); all 61 rounds won. Bigger than the
adjacency-build swaps because the n-source BFS *is* the whole cost — no post-processing to dilute it.

## Clippy note

My change is clippy-clean (0 findings in production ~42365-42383 / test ~71728-71872, grep-verified). The
crate has 12 pre-existing clippy `-D warnings` errors in peer/committed code — left untouched per
shared-checkout discipline.

## Files

- Production: `crates/fnx-algorithms/src/lib.rs` — `group_betweenness_centrality`.
- Test-only: `group_betweenness_idx_ab` A/B.

## Vein status

Tenth "name-keyed → integer" sub-family win. A float-returning centrality that is still **bit-identical**
because its per-source quantities are integer counts and the final sum order is fixed — the neighbour order
never touches the float accumulation. Lesson: a float output does not block the conversion when the
neighbour-order-sensitive intermediates are integers (counts/distances) and the float reduction runs in a
fixed index order.
