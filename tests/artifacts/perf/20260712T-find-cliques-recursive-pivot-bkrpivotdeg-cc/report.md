# br-r37-c1-bkrpivotdeg — find_cliques_recursive: precompute the BK pivot |N(u)∩P| once per pick

Status: **SHIP.** 1.7493x, byte-identical, STRICT gate. Twin of br-r37-c1-bkpivotdeg on the recursive BK
variant; 3rd comparator-recompute→precompute win.

## The target

`find_cliques_recursive(graph)` is recursive Bron-Kerbosch. Its inner `bron_kerbosch` chose the pivot in
`P ∪ X` maximising `|N(pivot) ∩ P|` via `p.union(x).max_by(comparator)` — and the comparator RECOMPUTED
`adj[u].intersection(p).count()` for BOTH sides. `max_by` recounts the running max's O(|P|) intersection on
every one of the ~|P∪X| comparisons.

## The lever

Precompute each candidate's `|N(u) ∩ P|` ONCE into a `HashMap<usize, usize>` (owned `usize`, borrows nothing),
then have the comparator read it. Identical fix to bkpivotdeg on the iterative `find_cliques`.

## Byte-identical argument

The `max_by` key is the identical `(|N(u) ∩ P|, u)` total order — same values, precomputed — so the same pivot
is chosen; the rest of BK (candidate set, recursion, X/P updates, index-sort of each clique + final list sort)
is unchanged. Verified: the A/B asserts `old_fn(&g) == super::find_cliques_recursive(&g)` (inline
comparator-recompute recursive BK — including the exact index-sort-then-stringify-then-list-sort output — vs the
shipped precompute) on 8 disjoint K₄₀ cliques; `test_find_cliques_recursive_matches_find_cliques` (asserting
`find_cliques_recursive == find_cliques`) + the recursive-suite tests pass.

## Median A/B (full function, paired-interleaved, one binary, NULL control)

`cargo test --release -p fnx-algorithms --lib find_cliques_recursive_pivot_ab -- --ignored --nocapture`

8 disjoint K₄₀ cliques (320 nodes) → large `P` at the top BK levels so the O(|P|²) pivot is a real fraction.
61 rounds. Ratio = recompute / precompute, **>1 = precompute faster**.

| row | median | win_rate | p5_p95 |
|-----|-------:|---------:|--------|
| `PRECOMPUTE_vs_recompute` | **1.7493x** | 61/61 | [1.5422, 1.9888] |
| `NULL_precompute_vs_precompute` | 0.9986x | 30/61 | [0.8796, 1.1543] |

Decisive: candidate p5 (1.54) is well above the null p95 (1.15) — clears the STRICT gate; all 61 rounds won;
null centred on 1.0. Matches the iterative twin (1.7383x).

## Files

- Production: `crates/fnx-algorithms/src/lib.rs` — `find_cliques_recursive` (inner `bron_kerbosch`).
- Test-only: `find_cliques_recursive_pivot_ab` A/B.

## Notes

- SHARED-FILE DISCIPLINE: a peer had concurrent uncommitted closeness_centrality work in the same file
  (`br-r37-c1-k4we4`/`yy0rp`). Committed ONLY my two hunks via a filtered `git apply --cached`; peer hunks left
  untouched. `lever.patch` here is exactly my staged hunks.
- Comparator-recompute→precompute sub-lever now 3 wins (mcapproxdeg, bkpivotdeg, bkrpivotdeg). BK pivot pair
  (iterative + recursive) both done. See [[naive_maxscan_to_buckets_lever]].
