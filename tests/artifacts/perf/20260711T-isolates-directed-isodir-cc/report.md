# br-r37-c1-isodir — `isolates_directed` no-alloc degree test

Status: **SHIP.** 8.16x median self-speedup, byte-identical. clippy clean.

## The target

`isolates_directed(digraph)` returns the nodes with no in- and no out-edges. The old
kernel, for EVERY node, allocated a `Vec<&str>` via `successors(node)` AND
`predecessors(node)` just to take `.len()` for the degree-zero test:

```rust
for &node in &nodes {
    let out_deg = graph.successors(node).map_or(0, |v| v.len());   // Vec<&str> alloc
    let in_deg  = graph.predecessors(node).map_or(0, |v| v.len()); // Vec<&str> alloc
    if out_deg == 0 && in_deg == 0 { result.push(node.to_string()); }
}
```

That is 2·V `Vec<&str>` allocations, while the output (the isolate list) is typically a
tiny fraction of V — so the allocations dominate.

## The lever

Use the no-alloc `out_degree_by_index`/`in_degree_by_index` (O(1) index-slice lengths).
The `neighbors_len_vec_alloc` family, applied per node.

## Byte-identical argument

`out_degree_by_index(i) == succ_indices[i].len() == successors(nodes[i]).len()` and
`in_degree_by_index(i) == pred_indices[i].len() == predecessors(nodes[i]).len()`, so the
`== 0 && == 0` test is the same, and the pushed node names (in `nodes_ordered()` order)
are unchanged. Verified in-test with `assert_eq!(isolates_directed, baseline)`.

## Median A/B (paired-interleaved, one binary, NULL control)

`cargo test --release -p fnx-algorithms --lib isolates_directed_isodir_ab -- --ignored --nocapture`

n=200000 nodes with a sparse path of edges over the first half (most nodes non-isolate,
the rest isolates; the degree test still runs for every node). 61 rounds. Ratio =
base/cand, **>1 means the no-alloc kernel is faster**.

| row | median | win_rate | p5_p95 |
|-----|-------:|---------:|--------|
| `NOALLOC_vs_string` | **8.1608x** | 61/61 | [6.7848, 9.3371] |
| `NULL_noalloc_vs_noalloc` | 1.0028x | 32/61 | [0.8663, 1.2744] |

The lever median (8.16x) clears the NULL floor: candidate p5 (6.78) is ~5x above the
NULL p95 (1.27), and every one of 61 paired rounds won. A clean win (NOT the
output-bound marginal) precisely because the 2·V `Vec<&str>` allocations dominate — the
isolate-list output is a tiny fraction.

## Gates

- clippy `-D warnings`: clean.
- A/B `cargo test --release` ran clean (ISODIR_AB line confirmed — not stale); parity
  green.
- pyo3 `isolates_directed` calls this kernel directly — the win reaches Python.

## Files

- Production: `crates/fnx-algorithms/src/lib.rs` — `isolates_directed`.
- Test-only: `isolates_directed_orig_string` baseline + `..._isodir_ab` A/B.
