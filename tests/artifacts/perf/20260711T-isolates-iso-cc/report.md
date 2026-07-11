# br-r37-c1-iso — `isolates` (undirected) no-alloc degree test

Status: **SHIP.** 7.33x median self-speedup, byte-identical. clippy clean.

## The target

`isolates(graph)` returns the degree-0 nodes. The old kernel allocated a `Vec<&str>`
via `neighbors(node)` per node just to check `is_empty()` — V allocations, while the
isolate output is a tiny fraction of V. (`number_of_isolates` calls `isolates`, so it
benefits automatically.)

## The lever

Use the no-alloc `neighbors_indices(i)` slice length (`.map_or(0, <[usize]>::len)`),
the undirected twin of the `isolates_directed` (br-r37-c1-isodir) lever.

## Byte-identical argument

`neighbors_indices(i).len() == neighbors(nodes[i]).len()`, and for the existing nodes
iterated here `neighbors` is always `Some`, so `len == 0` is exactly the old
"`Some(empty)` or `None` → isolate" test; the pushed node names (in `nodes_ordered()`
order) are unchanged. Verified in-test with `assert_eq!(isolates, baseline)`.

## Median A/B (paired-interleaved, one binary, NULL control)

`cargo test --release -p fnx-algorithms --lib isolates_iso_ab -- --ignored --nocapture`

n=200000 nodes, sparse path over the first half. 61 rounds. Ratio = base/cand, **>1
means no-alloc faster**.

| row | median | win_rate | p5_p95 |
|-----|-------:|---------:|--------|
| `NOALLOC_vs_string` | **7.3274x** | 61/61 | [5.9750, 9.3460] |
| `NULL_noalloc_vs_noalloc` | 1.0063x | 39/61 | [0.8357, 1.1279] |

The lever median (7.33x) clears the NULL floor: candidate p5 (5.98) is ~5x above the
NULL p95 (1.13), and every one of 61 paired rounds won. Clean (the V `Vec<&str>`
allocations dominate; the isolate output is a fraction).

## Gates

- clippy `-D warnings`: clean (batch pass verified this + isodir).
- A/B `cargo test --release` ran clean (ISO_AB line confirmed — not stale); parity green.
- pyo3 `isolates` calls this kernel directly — the win reaches Python.

## Files

- Production: `crates/fnx-algorithms/src/lib.rs` — `isolates`.
- Test-only: `isolates_orig_string` baseline + `..._iso_ab` A/B.
