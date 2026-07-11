# br-r37-c1-aperiod — `is_aperiodic` integer per-SCC GCD BFS

Status: **SHIP.** 2.05x median self-speedup, byte-identical (clears the null spread).

## The target

`is_aperiodic(digraph)` returns whether the graph's period (gcd of all cycle lengths)
is 1. For each non-trivial SCC it BFSes to assign levels, computing
`gcd(cycle_len)` over back edges (`cycle_len = level[u] - level[s] + 1`). The old
per-SCC BFS ran on a String-keyed `HashMap<&str, usize>` `dist` + `HashSet<&str>`
`scc_set` and called `successors(u)` (a `Vec<&str>` alloc per pop).

## The lever

Mark the SCC in a reusable `in_scc` bool array; key `dist`/`visited` by node index;
walk `successors_indices(u)`. `strongly_connected_components` (the shared subroutine)
is untouched.

## Byte-identical argument

`successors_indices(u)` yields the same successor order as `successors(u)`, so the BFS
visits identically → identical `dist`, identical tree/back-edge classification, and
identical `cycle_len` sequence — INCLUDING the pre-existing `usize` wraparound when a
back edge points one level ahead (`d_u - dist[s]` underflows, `+ 1` wraps to
`cycle_len == 0`, and `gcd(x, 0) == x`), which the integer path reproduces exactly.
`gcd` is commutative + associative, so even the accumulation order is irrelevant.
`in_scc[s]` reproduces `scc_set.contains(name)` (SCC nodes are valid graph nodes).
Verified in-test across a dense single-SCC graph (aperiodic → `true`, full BFS), a
pure 5-cycle (period 5 → `false`), and a 3-node DAG (all trivial SCCs → `true`).

## Median A/B (paired-interleaved, one binary, NULL control)

`cargo test --release -p fnx-algorithms --lib is_aperiodic_aperiod_ab -- --ignored --nocapture`

Dense single-SCC graph: spanning cycle + ~deg-10 chords per node, n=3000. 61 rounds.
Ratio = base/cand, **>1 means the integer kernel is faster**.

| row | median | win_rate | p5_p95 |
|-----|-------:|---------:|--------|
| `INT_vs_string` | **2.0534x** | 61/61 | [1.7353, 2.3293] |
| `NULL_int_vs_int` | 1.0066x | 34/61 | [0.8489, 1.2379] |

The lever median (2.05x) clears the NULL floor: candidate p5 (1.74) is above the NULL
p95 (1.24), and every one of 61 paired rounds won — a clean (if smaller) win. Smaller
than the other predicates because `strongly_connected_components` (integer compute +
component-name materialization) is an unconverted floor; the per-SCC BFS String work
the lever removes is a real fraction on top of it.

## Gates

- clippy `-D warnings`: clean (batch pass verified this + is_branching).
- A/B `cargo test --release` ran clean (APERIOD_AB line confirmed — not stale); parity
  across 3 graphs green.
- pyo3 `is_aperiodic` calls this kernel directly — the win reaches Python.

## Files

- Production: `crates/fnx-algorithms/src/lib.rs` — `is_aperiodic`.
- Test-only: `is_aperiodic_orig_string` baseline + `..._aperiod_ab` A/B.
