# br-r37-c1-bkpivotdeg — find_cliques: precompute the Bron-Kerbosch pivot |P∩N(u)| once per pick

Status: **SHIP.** 1.7383x, byte-identical, STRICT gate. Comparator-recompute → precompute-once sub-lever (same
shape as `mcapproxdeg`), on the hot core `find_cliques` (Bron-Kerbosch) kernel.

## The target

`find_cliques(graph)` is iterative Bron-Kerbosch with pivoting. At each stack frame it chooses the pivot in
`P ∪ X` that maximises `|P ∩ N(pivot)|` via `p.union(&x).max_by(comparator)` — and the comparator RECOMPUTED
`p.intersection(&adj[u]).count()` for BOTH sides. `max_by` holds a running maximum and compares it against every
other element, so the running max's O(|P|) intersection was recounted on every one of the ~|P∪X| comparisons.

## The lever

Precompute each candidate's `|P ∩ N(u)|` ONCE into a `HashMap<usize, usize>`, then have the comparator read
it. `counts` borrows `p`, so it is block-scoped to drop before `p` is moved into `p_mut`.

## Byte-identical argument

The `max_by` key is the identical `(|P ∩ N(u)|, u)` total order — same values, just precomputed — so it selects
the same pivot; the rest of BK (candidate set, recursion, X/P updates, final `cliques.sort()`) is unchanged.
Verified: the A/B asserts `old_fn(&g) == super::find_cliques(&g).cliques` (inline comparator-recompute BK vs the
shipped precompute) on 8 disjoint K₄₀ cliques; `test_find_cliques_recursive_matches_find_cliques` (which asserts
`find_cliques == find_cliques_recursive`, the latter unchanged) + the recursive-suite tests pass.

## Median A/B (full function, paired-interleaved, one binary, NULL control)

`cargo test --release -p fnx-algorithms --lib find_cliques_pivot_ab -- --ignored --nocapture`

8 disjoint K₄₀ cliques (320 nodes) → 8 maximal cliques but a large `P` (320) at the top BK levels, so the
O(|P|²) pivot selection is a real fraction. 61 rounds. Ratio = recompute / precompute, **>1 = precompute
faster**.

| row | median | win_rate | p5_p95 |
|-----|-------:|---------:|--------|
| `PRECOMPUTE_vs_recompute` | **1.7383x** | 61/61 | [1.4103, 2.1036] |
| `NULL_precompute_vs_precompute` | 1.0049x | 33/61 | [0.8758, 1.0888] |

Decisive: candidate p5 (1.41) is well above the null p95 (1.09) — clears the STRICT gate; all 61 rounds won;
null centred on 1.0. The pivot precompute is a big fraction here because the running max's intersection was
recomputed O(|P∪X|) times against a large `P`.

## Files

- Production: `crates/fnx-algorithms/src/lib.rs` — `find_cliques`.
- Test-only: `find_cliques_pivot_ab` A/B.

## Vein status

2nd comparator-recompute→precompute win (after `max_clique_approx`/mcapproxdeg). The same fix likely applies to
`find_cliques_recursive` (32996, twin BK pivot) — a natural next candidate. LEVER: any `max_by`/`min_by` whose
comparator recomputes an expensive key on both sides → precompute once, compare precomputed values. See
[[naive_maxscan_to_buckets_lever]] (comparator-precompute sub-lever note).
