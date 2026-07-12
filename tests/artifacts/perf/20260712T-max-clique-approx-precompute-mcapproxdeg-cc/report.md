# br-r37-c1-mcapproxdeg — max_clique_approx: precompute candidate degree once per round (drop comparator recompute + Vec allocs)

Status: **SHIP.** 1.7071x, byte-identical, STRICT gate.

## The target

`max_clique_approx(graph)` greedily grows a clique: each round it picks the candidate with the most neighbours
inside the current candidate set (ties by max name). It found that candidate with
`candidates.iter().max_by(comparator)` where the comparator RECOMPUTED both sides' degree — each a fresh
`graph.neighbors(x)` `Vec<&str>` **allocation** plus a `candidates.contains` filter. `max_by` holds a running
maximum and compares it against every other element, so the running max's degree (a full neighbours scan +
alloc) was recomputed ~|candidates| times per round — O(|candidates|) redundant allocations + rescans.

## The lever

Precompute each candidate's degree-within-candidates ONCE per round into a `HashMap<&str, usize>` using
`neighbors_iter` (no `Vec` allocation), then have the `max_by` comparator just read the precomputed value.
`deg` is scoped to a block so it (which borrows `candidates`) drops before the `candidates.remove`/`retain`
mutation.

## Byte-identical argument

The `max_by` key is the identical `(degree, name)` total order — same values, just precomputed instead of
recomputed — so it selects the same node (max degree, ties by max name). The rest of the loop (remove chosen,
retain chosen's neighbours) is unchanged. Verified: the A/B asserts `old_fn(&g) == super::max_clique_approx(&g)`
(inline comparator-recompute version vs the shipped precompute) on a dense 1200-node graph; all 6 max_clique
suite tests pass (complete, triangle_plus, empty, + 3 make_max_clique_graph).

## Median A/B (full function, paired-interleaved, one binary, NULL control)

`cargo test --release -p fnx-algorithms --lib max_clique_approx_deg_ab -- --ignored --nocapture`

Dense circulant (1200 nodes, degree 120 → large candidate set → many redundant comparator recomputes). 61
rounds. Ratio = recompute / precompute, **>1 = precompute faster**.

| row | median | win_rate | p5_p95 |
|-----|-------:|---------:|--------|
| `PRECOMPUTE_vs_recompute` | **1.7071x** | 61/61 | [1.5196, 2.1943] |
| `NULL_precompute_vs_precompute` | 1.0059x | 32/61 | [0.7267, 1.1666] |

Decisive: candidate p5 (1.52) is above the null p95 (1.17) — clears the STRICT gate; all 61 rounds won; null
centred on 1.0. Bigger than a naive "2× the comparator recompute" because it also eliminates the ~|candidates|
per-round `neighbors()` `Vec` allocations (replaced by alloc-free `neighbors_iter`).

## Files

- Production: `crates/fnx-algorithms/src/lib.rs` — `max_clique_approx`.
- Test-only: `max_clique_approx_deg_ab` A/B.

## Notes

- SHARED-FILE DISCIPLINE: a peer had concurrent uncommitted work in the same file (`br-r37-c1-uxbg8`, Prüfer
  decoder). Committed ONLY my two hunks via a filtered `git apply --cached` (never `git add <file>`); the
  peer's hunks were left untouched in the working tree. `lever.patch` here contains exactly my staged hunks.
- LEVER PATTERN: `max_by`/`min_by` whose comparator recomputes an expensive per-element key on BOTH sides
  (recomputing the running max O(n) times) → precompute the key once, then compare precomputed values.
  Distinct from the O(V²)→bucket lever; this keeps the O(n) scan but removes the redundant recomputation +
  allocations.
