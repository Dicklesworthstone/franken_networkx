# br-r37-c1-branch — `is_branching` no-alloc degrees + integer per-component edge count

Status: **SHIP.** 2.28x median self-speedup, byte-identical (clears the null spread).

## The target

`is_branching(digraph)` checks whether a DiGraph is a branching (forest of
arborescences): every node has in-degree ≤ 1, at most n-1 edges, and each weakly
connected component is a tree (exactly |comp|-1 intra-component edges). The old kernel
took `predecessors(node).len()`/`successors(node).len()` (`Vec<&str>` allocs) per node
for the degree check, and for each WCC built a `HashSet<&str>` and walked
`successors_iter(name)` with String `contains`.

## The lever

No-alloc `in_degree_by_index`/`out_degree_by_index` for degrees; a reusable
`Vec<bool>` component mark array + `successors_indices` for the per-component edge
count (mark the component's node indices, count successors that land in it, unmark).
`weakly_connected_components` (already integer-optimized) is unchanged.

## Byte-identical argument

`in_degree == predecessors().len()`, `out_degree == successors().len()`, so the
`in_deg > 1` early-return (node-index order) and `edge_count` match. WCC components are
valid graph nodes, so every name resolves to an index; `comp_edges` counts the same
intra-component directed edges (`successor ∈ comp`), and `comp_len` is the same. The
boolean result is unchanged (integer counts, no float). Verified in-test across the
true path (rooted binary tree → `true`, full scan) and both false paths (a node with
in-degree 2 → `false`, and a 3-cycle component with `comp_edges != comp_len-1` →
`false`).

## Median A/B (paired-interleaved, one binary, NULL control)

`cargo test --release -p fnx-algorithms --lib is_branching_branch_ab -- --ignored --nocapture`

Rooted binary tree on n=60000 (a branching). 61 rounds. Ratio = base/cand, **>1 means
the integer kernel is faster**.

| row | median | win_rate | p5_p95 |
|-----|-------:|---------:|--------|
| `INT_vs_string` | **2.2840x** | 61/61 | [2.0187, 2.7357] |
| `NULL_int_vs_int` | 0.9826x | 26/61 | [0.8543, 1.2248] |

The lever median (2.28x) clears the NULL floor: candidate p5 (2.02) is above the NULL
p95 (1.22), and every one of 61 paired rounds won — a clean (if smaller) win, NOT the
overlapping-distribution marginal seen for output-bound functions. Smaller than the
other directed predicates because `weakly_connected_components` (integer compute) plus
its `Vec<Vec<String>>` component materialization is an unconverted floor; the degree +
per-component String work the lever removes is a real fraction on top of it.

## Gates

- clippy `-D warnings`: clean.
- A/B `cargo test --release` ran clean (BRANCH_AB line confirmed present — not stale);
  parity across 3 graphs green.
- pyo3 `is_branching` calls this kernel directly — the win reaches Python.

## Files

- Production: `crates/fnx-algorithms/src/lib.rs` — `is_branching`.
- Test-only: `is_branching_orig_string` baseline + `..._branch_ab` A/B.
