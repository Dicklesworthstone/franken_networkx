# br-r37-c1-tourn — `is_tournament` snapshot integer successor sets

Status: **SHIP.** 17.37x median self-speedup, byte-identical. clippy clean.

## The target

`is_tournament(digraph)` checks whether every ordered pair of nodes has exactly one
of the two directed edges. The old kernel called `digraph.successors(nodes[i])` (a
fresh `Vec<&str>` alloc) **inside the O(V²) pair loop** — once for the i-side and
once for the j-side of *every* pair — then linear-searched with
`s.contains(&nodes[j])` (String comparison). That is O(V³) time with O(V²) `Vec<&str>`
allocations.

## The lever

Snapshot `Vec<HashSet<usize>>` of successor indices ONCE (via `successors_indices`),
then probe `succ_sets[i].contains(&j)` / `succ_sets[j].contains(&i)` in O(1). This is
both an allocation elimination (O(V²) `Vec<&str>` → 0 in the loop) AND an algorithmic
improvement (O(V³) → O(V²)).

## Byte-identical argument

The out-degree sum (`HashSet::len` == `successors().len()` for a simple DiGraph),
`expected_edges`, and the `has_ij`/`has_ji` booleans (`j ∈ succ(i)` / `i ∈ succ(j)`)
are the same set-membership facts, so the pure structural `true`/`false` result is
unchanged (no float, no order dependence). Verified in-test across the true path
(transitive tournament → `true`, full pair scan) and both false paths (a
non-tournament with a missing edge, and one with a 2-cycle → `has_ij == has_ji`): all
three `assert_eq!(is_tournament, baseline)`; the existing
`test_is_tournament{,_not,_empty_is_true}` unit tests are green.

## Median A/B (paired-interleaved, one binary, NULL control)

`cargo test --release -p fnx-algorithms --lib is_tournament_tourn_ab -- --ignored --nocapture`

Transitive tournament on n=300 (edge i→j for every i<j → full O(V²) pair scan). 61
rounds. Ratio = base/cand, **>1 means the snapshot kernel is faster**.

| row | median | win_rate | p5_p95 |
|-----|-------:|---------:|--------|
| `SNAP_vs_string` | **17.3681x** | 61/61 | [13.5239, 21.6971] |
| `NULL_snap_vs_snap` | 1.0177x | 38/61 | [0.8260, 1.2045] |

The lever median (17.37x) dwarfs the NULL floor: candidate p5 (13.52) is ~11x above
the NULL p95 (1.20), and every one of 61 paired rounds won. A clean heavy win (bool
output → no materialization floor), unlike the edge-emitting / edges_ordered-bound
functions.

## Gates

- clippy `-D warnings`: clean (attempt 1).
- A/B `cargo test --release` ran clean; 3 unit tests + parity across 3 graphs green.
- pyo3 `is_tournament` calls this kernel directly — the win reaches Python.

## Files

- Production: `crates/fnx-algorithms/src/lib.rs` — `is_tournament`.
- Test-only: `is_tournament_orig_string` baseline + `..._tourn_ab` A/B.
