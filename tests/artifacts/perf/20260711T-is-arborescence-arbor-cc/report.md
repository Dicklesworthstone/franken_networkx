# br-r37-c1-arbor — `is_arborescence` no-alloc degrees + integer BFS

Status: **SHIP.** 41.27x median self-speedup, byte-identical. clippy clean.

## The target

`is_arborescence(digraph)` checks whether a DiGraph is a rooted tree: every node has
in-degree 0 (one root) or 1, exactly n-1 edges, and is weakly connected. The old
kernel took `predecessors(node).len()`/`successors(node).len()` (`Vec<&str>` allocs)
per node for the degree check, and ran the weak-connectivity BFS over `successors()`/
`predecessors()` (`Vec<&str>` allocs per pop) with a `HashSet<&str>` visited.

## The lever

Use the no-alloc `in_degree_by_index`/`out_degree_by_index` for degrees, and walk
`successors_indices`/`predecessors_indices` with a `Vec<bool>` visited + running
count in the BFS.

## Byte-identical argument

`in_degree == predecessors().len()` and `out_degree == successors().len()` (both are
the index-slice lengths), so `edge_count`/`root_count`/the `in_deg` checks — and the
node-index-order point of any early `false` return — are the same integers. The BFS
reaches the same node set (ignoring direction), so `count == n` is the same boolean.
Output is a `bool` (no float, no order dependence). Verified in-test across the true
path (rooted binary tree → `true`, full scan) and both false paths (a graph with a
2-cycle, and a disconnected pair of trees → `false`): all three
`assert_eq!(is_arborescence, baseline)`; the existing
`test_is_arborescence_{empty,simple_tree,not_tree,cycle}` unit tests are green.

## Median A/B (paired-interleaved, one binary, NULL control)

`cargo test --release -p fnx-algorithms --lib is_arborescence_arbor_ab -- --ignored --nocapture`

Rooted binary tree on n=60000 (parent (i-1)/2 → i). 121 rounds. Ratio = base/cand,
**>1 means the no-alloc kernel is faster**.

| row | median | win_rate | p5_p95 |
|-----|-------:|---------:|--------|
| `NOALLOC_vs_string` | **41.2724x** | 121/121 | [16.4750, 73.7129] |
| `NULL_noalloc_vs_noalloc` | 1.0115x | 63/121 | [0.1508, 1.3886] |

The lever median (41.27x) dwarfs the NULL floor: candidate p5 (16.48) is ~12x above
the NULL p95 (1.39), and every one of 121 paired rounds won. Large because on a
60,000-node graph the baseline's `HashSet<&str>` BFS (String insert/probe per node)
plus 2n `Vec<&str>` degree allocations dominate — all removed by the `Vec<bool>` +
no-alloc-degree kernel. (A `bool`-output predicate → no materialization floor.)

## Note — stale-binary trap

The first `--include-ignored` run served a STALE rch test binary (only the 4
pre-lever unit tests ran, "finished in 0.01s", the `_arbor_ab` test absent). A
forced fresh recompile (`Compiling fnx-algorithms`) then ran the real measurement.
Always confirm the A/B test name appears in the run before trusting a result.

## Gates

- clippy `-D warnings`: clean.
- A/B `cargo test --release` (fresh build) ran clean; 4 unit tests + parity across 3
  graphs green.
- pyo3 `is_arborescence` calls this kernel directly — the win reaches Python.

## Files

- Production: `crates/fnx-algorithms/src/lib.rs` — `is_arborescence`.
- Test-only: `is_arborescence_orig_string` baseline + `..._arbor_ab` A/B.
