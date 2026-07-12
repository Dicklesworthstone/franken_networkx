# br-r37-c1-snapidx — snap_aggregation refinement-loop integer swap

Status: **SHIP.** 3.23x (on the refinement pass), byte-identical. My change clippy-clean (crate has
pre-existing peer lint debt, untouched).

## The target

`snap_aggregation(graph, node_attributes)` (fnx-algorithms) — SNAP graph summarization. Its **iterative
refinement** (`for _ in 0..n` — up to n passes) recomputes, for every node each pass, a neighbour-group
signature by iterating neighbours **by name**: `graph.neighbors(nodes[i])` (a `Vec<&str>` alloc) +
`idx.get(nb)` (a String re-hash per edge) → `group_of[ni]`. That's `O(passes · n · deg)` String work.

## The lever

Walk `graph.neighbors_indices(i)` (zero-alloc `&[usize]`) and read `group_of[ni]` directly. The `idx` map is
left in place — it is still used once, in the O(E) summary-edge loop.

## Byte-identical argument

`nodes[i]` sits at internal index `i` (the `idx` map is `nodes_ordered().enumerate()`), so
`neighbors_indices(i)` yields exactly node i's neighbours. Every neighbour is a graph node, so the old
`idx.get(nb)` was always `Some`; the collected `nbr_groups` multiset is identical, and after `sort` + `dedup`
the signature `(group_of[i], nbr_groups)` is identical. Since the pass iterates `i` in `0..n` (same order),
the new group-id assignment is identical → the whole refinement converges to the same `group_of` → the same
summary graph. Verified: A/B **resulting-grouping parity** `assert_eq!(old, new)` (one refinement pass, old
`neighbors`+`idx.get` vs new `neighbors_indices`) passed before timing; the 3 snap_aggregation suite tests
pass, including `test_snap_aggregation_groups_by_attr` (which checks the summary graph).

## Median A/B (paired-interleaved, one binary, NULL control)

`cargo test --release -p fnx-algorithms --lib snap_aggregation_idx_ab -- --ignored --nocapture`

One refinement pass over a 50000-node circulant (degree 20) with a 100-group seed. This is the exact hot loop
the full function runs up to n times, so its speedup is proportional. 61 rounds. Ratio = string/index, **>1 =
index faster**.

| row | median | win_rate | p5_p95 |
|-----|-------:|---------:|--------|
| `INT_vs_string` | **3.2252x** | 61/61 | [2.9294, 3.8421] |
| `NULL_int_vs_int` | 0.9985x | 30/61 | [0.8742, 1.1201] |

Decisive: candidate p5 (2.93) ~2.6x above the NULL p95 (1.12); all 61 rounds won.

## Clippy note

My change is clippy-clean (0 findings in production ~42670-42684 / test ~71479-71592, grep-verified). The
crate has 12 pre-existing clippy `-D warnings` errors in peer/committed code — left untouched per
shared-checkout discipline.

## Files

- Production: `crates/fnx-algorithms/src/lib.rs` — `snap_aggregation` (refinement loop).
- Test-only: `snap_aggregation_idx_ab` A/B.

## Vein status

Eighth "name-keyed → integer" sub-family win. Distinct: the residual was in a genuinely HOT loop (up to n
refinement passes), not just setup. `idx` was kept (needed elsewhere) — a partial conversion of only the hot
path. Next of the grep: `generic_bfs_edges` (verify BFS-edge output order first).
