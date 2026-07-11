# br-r37-c1-gmodmat — `greedy_modularity_communities` materialize edges once

Status: **SHIP (modest).** 1.1538x median, 56/61 win rate (sign-test decisive), byte-identical.

## The target

`greedy_modularity_communities` (CNM) is fully integer-indexed already, but its setup called
`graph.edges_ordered_borrowed()` **three times** (for `m`, for `degree`, for the dq-init) —
lines 24195/24209/24240. Each call rebuilds a full `Vec<(&str,&str,&AttrMap)>` of size |E|
with a per-edge `edges.get(&(u,t))` HashMap lookup. So 2 of the 3 rebuilds are pure
redundant O(E) work (plus allocator/cache pressure from the throwaway Vecs).

## Profile-first (hotspot ranking)

A `#[ignore]` profile (n=5000, |E|=20050) measured the redundant share directly:
`full_median=0.0412s`, one materialization `mat1=0.00149s`. The 2 redundant rebuilds are
~7.2% of runtime by the conservative `2·mat1` estimate — above the null floor, worth a real
A/B (the end-to-end A/B then showed a larger effect once allocator/cache pressure is
included). The rest of the function (the O(E log E) heap merge loop) is unchanged.

## The lever

Refactored into `greedy_modularity_communities_impl(.., single_materialize)`. Production
passes `true`: materialize `edges_ordered_borrowed()` ONCE into `cached_edges` and drive the
three setup passes over it via a `for_each_edge!` macro. The baseline path (`false`, used
only by the A/B) rebuilds per pass — the pre-lever behaviour. Both share the exact same impl
body (merge loop, result), so parity is byte-identical by construction.

## Byte-identical argument

`single_materialize` changes ONLY where the setup edges come from — the same edges, in the
same `edges_ordered_borrowed()` order, drive identical `m`/`degree`/`dq` accumulation
(f64 sums in the same order → identical bits). The merge loop and community collection are
literally the same code. Verified in-test with
`assert_eq!(impl(..true), impl(..false))`.

## Median A/B (paired-interleaved, one binary, NULL control)

`cargo test --release -p fnx-algorithms --lib greedy_modularity_gmodmat_ab -- --ignored --nocapture`

n=5000 (50 communities × 100), |E|=20050. 61 rounds. Ratio = base/cand, **>1 = materialize-once faster**.

| row | median | win_rate | p5_p95 |
|-----|-------:|---------:|--------|
| `MAT1_vs_MAT3` | **1.1538x** | 56/61 | [0.9648, 1.4251] |
| `NULL_mat1_vs_mat1` | 0.9983x | 29/61 | [0.8779, 1.1906] |

**Why this ships as a modest win, not a clean one:** greedy_modularity's total runtime is
variable (the heap merge loop + per-merge HashMap churn), so the NULL is wide ([0.88, 1.19]).
By the strict magnitude criterion (candidate p5 > null p95) this is NOT clean — candidate p5
(0.965) overlaps the null. BUT the paired **sign test is decisive**: the candidate won 56/61
rounds vs the null's 29/61 (≈50%); under H0 (no effect) P(≥56/61) < 1e-9. The direction is
certain and the magnitude is ~1.15x (the wide null makes the exact magnitude ±~15%). This is
the same modest-but-real tier as the shipped `bfs_beam_edges` (1.089x).

## Gates

- A/B `cargo test --release` ran on a real worker (GMODMAT_AB line present — not stale);
  parity `assert_eq!` green.
- clippy `-D warnings`: diff clean (see clippy log; pre-existing crate debt only).
- pyo3 `greedy_modularity_communities` calls this kernel directly — the win reaches Python.

## Files

- Production: `crates/fnx-algorithms/src/lib.rs` — `greedy_modularity_communities` (wrapper) +
  `greedy_modularity_communities_impl` (`single_materialize=true`).
- Test-only: `greedy_modularity_gmodmat_ab` A/B (parity + paired median).

## Family note

This reopens a NEW lever family: **redundant same-graph `edges_ordered_borrowed()`/`edges_ordered()`
rebuilds**. A sweep found the other multi-call sites materialize DIFFERENT graphs (union/compose/
product/isomorphic — g1 vs g2, not redundant). `greedy_modularity_communities` was the only
same-graph 3× site in cc lane. `edge_current_flow_betweenness` (2×) and `is_planar` (2×) are the
remaining same-graph candidates to check next.
