# br-r37-c1-idc — `in_degree_centrality` no-alloc in-degree

Status: **SHIP.** 11.36x median self-speedup, byte-identical. Diff clippy-clean.

## The target

`in_degree_centrality(digraph)` maps every node to `(name, in_deg / (n-1))`. The old
kernel took the in-degree with `digraph.predecessors(node).map(|it| it.len()).unwrap_or(0)`
— a `Vec<&str>` allocation per node, built only to read its `.len()`. V allocations
discarded immediately.

## The lever

Iterate `nodes_ordered()` with `.enumerate()` and take the in-degree with the no-alloc
`digraph.in_degree_by_index(i)` (an O(1) index-slice length). Directed twin of
`out_degree_centrality` (br-r37-c1-odc); the `neighbors_len_vec_alloc` family.

## Byte-identical argument

`in_degree_by_index(i) == predecessors(nodes[i]).len()` for every existing node, and
`nodes_ordered()` fixes the iteration order, so each `(node.to_owned(), in_deg / denom)`
pair is unchanged — same names, same scores, same order. The `n == 0` (empty) and
`n == 1` (score 1.0, early return before `denom`) branches are preserved verbatim.
Verified in-test with `assert_eq!(in_degree_centrality, in_degree_centrality_orig_string)`.

## Median A/B (paired-interleaved, one binary, NULL control)

`cargo test --release -p fnx-algorithms --lib in_degree_centrality_idc_ab -- --ignored --nocapture`

n=100000 directed nodes, out-degree ~8 (so in-degrees are non-trivial). 61 rounds.
Ratio = base/cand, **>1 means the no-alloc kernel is faster**.

| row | median | win_rate | p5_p95 |
|-----|-------:|---------:|--------|
| `NOALLOC_vs_string` | **11.3636x** | 61/61 | [5.0028, 15.8466] |
| `NULL_noalloc_vs_noalloc` | 1.0009x | 31/61 | [0.3940, 2.3839] |

The lever median (11.36x) clears the NULL floor: candidate p5 (5.00) is above the NULL p95
(2.38), and every one of 61 paired rounds won. The NULL was noisier on this worker (wide
[0.39, 2.38] spread), but the candidate distribution sits entirely above it — 61/61 with a
median 11.4x cannot come from the ~1.0-centred null. A **clean** win (twin of ODC 11.38x):
the per-node `Vec<&str>` allocation dominates the per-node `node` String clone.

## Gates

- clippy `-D warnings` — **this diff is clean**. The scoped `cargo clippy -p fnx-algorithms
  --lib --tests -- -D warnings` reports only the same pre-existing crate debt as ODC
  (10× `doc_lazy_continuation` at lines 13598–42546 + 1× `collapsible_if`, all in untouched
  functions). My additions (baseline fn ~31224, A/B test ~51078) contain zero doc-list
  items and no nested ifs — a whole-file range scan confirms none in my ranges — so the
  finding count is unchanged. Pre-existing debt masked by the `ftui` `--all-targets` flake;
  out of scope for a degree-centrality body swap.
- A/B `cargo test --release` ran clean on a real worker (IDC_AB line confirmed present —
  not a stale binary); parity `assert_eq!` green.
- pyo3 `in_degree_centrality` calls this kernel directly — the win reaches Python.

## Files

- Production: `crates/fnx-algorithms/src/lib.rs` — `in_degree_centrality`.
- Test-only: `in_degree_centrality_orig_string` baseline + `..._idc_ab` A/B.

## Family status

With ODC (out) + IDC (in) shipped and the undirected `degree_centrality` already no-alloc
(`neighbor_count`) and `degree_centrality_directed` already using `out_degree`/`in_degree`
(name-keyed, no Vec alloc), the degree-centrality corner of the `neighbors_len_vec_alloc`
family is now COMPLETE.
