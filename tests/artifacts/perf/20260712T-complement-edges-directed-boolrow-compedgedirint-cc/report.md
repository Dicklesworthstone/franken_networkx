# br-r37-c1-compedgedirint — complement_edges_directed O(V²) has_edge → bool-row

Status: **SHIP.** 3.13x, byte-identical. Directed sibling of `br-r37-c1-compedgeidx`. My change clippy-clean
(crate has pre-existing peer lint debt, untouched).

## The target

`complement_edges_directed(digraph)` (fnx-algorithms) yields every directed non-edge: `for u, for v, if u!=v
&& !has_edge(u, v) push` — a String hash of both endpoints for every one of the `O(V²)` **ordered** pairs.

## The lever — bool-row via successors

For each source `i`, mark its **successors** in a reusable `is_succ: vec![false; n]` row (via
`successors_indices(i)`, zero-alloc), then test with an O(1) array read `is_succ[j]`; reset after. (Directed
edge `u→v` exists ⟺ `v` is a successor of `u`.)

## Byte-identical argument

`nodes[i]` sits at internal index `i`, so `successors_indices(i)` are exactly `nodes[i]`'s successors →
`is_succ[j]` ⟺ `has_edge(nodes[i], nodes[j])`. Thus `!is_succ[j]` ⟺ `!has_edge`, and the `(i, j != i)` ordered
pairs are pushed in the identical row-major order with the same names. Verified: A/B **output-list parity**
`assert_eq!(old, new)` (inline old-`has_edge` scan vs new-bool-row, exact `Vec<(String,String)>` equality on a
2000-node dense directed circulant) passed before timing; the `complement_directed_test` (+ 8 more complement)
suite tests pass.

## Median A/B (paired-interleaved, one binary, NULL control)

`cargo test --release -p fnx-algorithms --lib complement_edges_directed_idx_ab -- --ignored --nocapture`

Dense directed circulant (2000 nodes, out-degree 1200 → 60% density, so the `has_edge` scan over all 4M
ordered pairs dominates). 61 rounds. Ratio = has_edge/bool-row, **>1 = bool-row faster**.

| row | median | win_rate | p5_p95 |
|-----|-------:|---------:|--------|
| `BOOLROW_vs_hasedge` | **3.1313x** | 61/61 | [2.7116, 3.5808] |
| `NULL_boolrow_vs_boolrow` | 1.0012x | 31/61 | [0.8952, 1.1117] |

Decisive: candidate p5 (2.71) ~2.4x above the NULL p95 (1.11); all 61 rounds won.

## Clippy note

My change is clippy-clean (0 findings in production ~21608-21630 / test ~72205-72324, grep-verified). The
crate has 12 pre-existing clippy `-D warnings` errors in peer/committed code — left untouched per
shared-checkout discipline.

## Files

- Production: `crates/fnx-algorithms/src/lib.rs` — `complement_edges_directed`.
- Test-only: `complement_edges_directed_idx_ab` A/B.

## Vein status

Third win in the `has_edge`-in-nested-loop sub-family; the complement_edges pair (undirected + directed) is
now bool-row. The lever: any `for i { for j { has_edge(nodes[i], nodes[j]) }}` non-edge/pair scan → mark one
endpoint's `neighbors_indices`/`successors_indices` in a reusable bool row, test with an O(1) array read.
