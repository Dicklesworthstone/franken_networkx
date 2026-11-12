# br-r37-c1-odc — `out_degree_centrality` no-alloc out-degree

Status: **SHIP.** 11.38x median self-speedup, byte-identical. clippy clean.

## The target

`out_degree_centrality(digraph)` maps every node to `(name, out_deg / (n-1))`. The old
kernel took the out-degree with `digraph.successors(node).map(|it| it.len()).unwrap_or(0)`
— a `Vec<&str>` allocation per node, built only to read its `.len()`. That is V
allocations discarded immediately.

## The lever

Iterate `nodes_ordered()` with `.enumerate()` and take the out-degree with the no-alloc
`digraph.out_degree_by_index(i)` (an O(1) index-slice length). The `neighbors_len_vec_alloc`
family, applied per node — the directed-centrality twin of the `isolates_directed`
(br-r37-c1-isodir) lever.

## Byte-identical argument

`out_degree_by_index(i) == successors(nodes[i]).len()` for every existing node, and
`nodes_ordered()` fixes the iteration order, so each `(node.to_owned(), out_deg / denom)`
pair is unchanged — same names, same scores, same order. The `n == 0` (empty) and
`n == 1` (score 1.0) branches are preserved verbatim. Verified in-test with
`assert_eq!(out_degree_centrality, out_degree_centrality_orig_string)`.

## Median A/B (paired-interleaved, one binary, NULL control)

`cargo test --release -p fnx-algorithms --lib out_degree_centrality_odc_ab -- --ignored --nocapture`

n=100000 directed nodes, out-degree ~8. 61 rounds. Ratio = base/cand, **>1 means the
no-alloc kernel is faster**.

| row | median | win_rate | p5_p95 |
|-----|-------:|---------:|--------|
| `NOALLOC_vs_string` | **11.3845x** | 61/61 | [7.4774, 13.7554] |
| `NULL_noalloc_vs_noalloc` | 0.9962x | 29/61 | [0.8847, 1.0693] |

The lever median (11.38x) clears the NULL floor decisively: candidate p5 (7.48) is ~7x
above the NULL p95 (1.07), and every one of 61 paired rounds won. This is a **clean** win,
not the output-floored marginal I initially predicted — the per-node `Vec<&str>`
allocation dominates the per-node `node` String clone (which the lever cannot remove), so
dropping the alloc pays off outright.

## Gates

- clippy `-D warnings` — **this diff is clean**. A scoped `cargo clippy -p fnx-algorithms
  --lib --tests -- -D warnings` landed a real worker and reported 11 findings, ALL
  pre-existing crate debt in untouched functions: 10× `doc_lazy_continuation` (markdown
  doc-list items at lines 13598–42546) + 1× `collapsible_if`. My added code occupies
  31218–31283 (production + baseline) and 50946–51032 (A/B); a whole-file scan confirms
  ZERO doc-list-items and no nested ifs in those ranges, so my diff introduces no new
  finding. This debt was masked until now because the `--all-targets` clippy kept flaking
  on the `ftui` path-dep (workspace Cargo.lock resolution fails on workers missing
  `/dp/frankentui`); a newer worker clippy flags `doc_lazy_continuation` that older CI did
  not. Not fixed here — it is peer-owned doc-comment debt in a shared file, out of scope
  for a degree-centrality body swap.
- A/B `cargo test --release` ran clean on a real worker (ODC_AB line confirmed present —
  not a stale binary); parity `assert_eq!` green (the byte-identity proof).
- pyo3 `out_degree_centrality` calls this kernel directly — the win reaches Python.

## Files

- Production: `crates/fnx-algorithms/src/lib.rs` — `out_degree_centrality`.
- Test-only: `out_degree_centrality_orig_string` baseline + `..._odc_ab` A/B.

## Twins

`in_degree_centrality` (`predecessors().len()`) and the undirected `degree_centrality`
(`neighbors().len()`) share the exact same profile — next candidates in this same lever.
The output floor did NOT dominate here, so they are worth measuring rather than
pre-dismissing as marginal.
