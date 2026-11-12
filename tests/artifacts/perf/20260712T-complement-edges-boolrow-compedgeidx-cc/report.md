# br-r37-c1-compedgeidx — complement_edges O(V²) has_edge → bool-row

Status: **SHIP.** 3.62x, byte-identical. Second win in the `has_edge`-in-nested-loop sub-family (after
modularity). My change clippy-clean (crate has pre-existing peer lint debt, untouched).

## The target

`complement_edges(graph)` (fnx-algorithms) yields every non-edge: `for i, for j>i, if !has_edge(nodes[i],
nodes[j]) push`. The `has_edge(u, v)` String-hashes both endpoints for **every** one of the `O(V²)` pairs.

## The lever — bool-row (array beats hash)

For each source `i`, mark its neighbours in a reusable `is_nbr: vec![false; n]` row (via
`neighbors_indices(i)`, zero-alloc), then test membership with an **O(1) array read** `is_nbr[j]`; reset the
row after. Unlike modularity's `has_edge`→`HashMap` (marginal — both hash), here the replacement is a plain
bool-array access, which is strictly faster than the `has_edge` hash.

## Byte-identical argument

`nodes[i]` sits at internal index `i`, so `neighbors_indices(i)` are exactly `nodes[i]`'s neighbours →
`is_nbr[j]` ⟺ `nodes[j]` is a neighbour of `nodes[i]` ⟺ `has_edge(nodes[i], nodes[j])`. Thus `!is_nbr[j]` ⟺
`!has_edge`, and the `(i, j>i)` pairs are pushed in the identical row-major order with the same names.
Verified: A/B **output-list parity** `assert_eq!(old, new)` (inline old-`has_edge` scan vs new-bool-row, exact
`Vec<(String,String)>` equality on a 2500-node dense circulant) passed before timing; the 9 complement suite
tests pass.

## Median A/B (paired-interleaved, one binary, NULL control)

`cargo test --release -p fnx-algorithms --lib complement_edges_idx_ab -- --ignored --nocapture`

Dense circulant (2500 nodes, degree 1600 → ~64% density, so the `has_edge` scan over all 3.1M pairs dominates
the non-edge pushes). 61 rounds. Ratio = has_edge/bool-row, **>1 = bool-row faster**.

| row | median | win_rate | p5_p95 |
|-----|-------:|---------:|--------|
| `BOOLROW_vs_hasedge` | **3.6188x** | 61/61 | [3.1859, 4.1786] |
| `NULL_boolrow_vs_boolrow` | 0.9991x | 30/61 | [0.8819, 1.2272] |

Decisive: candidate p5 (3.19) ~2.6x above the NULL p95 (1.23); all 61 rounds won.

## Clippy note

My change is clippy-clean (0 findings in production ~21571-21595 / test ~72066-72185, grep-verified). The
crate has 12 pre-existing clippy `-D warnings` errors in peer/committed code — left untouched per
shared-checkout discipline.

## Files

- Production: `crates/fnx-algorithms/src/lib.rs` — `complement_edges`.
- Test-only: `complement_edges_idx_ab` A/B.

## Vein status

Second win in the `has_edge`-in-nested-loop sub-family. Sharpens the modularity lesson: `has_edge`→`HashMap`
is marginal (both hash), but `has_edge`→**bool array row** (when you iterate one endpoint and can mark the
other's neighbours) is a real win — array read vs hash. Note: the sibling `complement` (21538) has the same
loop but is **bypassed** (no pyo3 call — a `//` comment references it as "legacy … materialized"), so it was
left. Next: `complement_edges_directed` (same pattern, reached), and other `for i { for j>i { has_edge }}`
non-edge / triangle scans.
