# br-r37-c1-isotri — `could_be_isomorphic` integer-adjacency + mark-array triangle count

Status: **SHIP.** 11.75x median self-speedup on the triangle-count kernel, byte-identical.

## The target

`could_be_isomorphic(g1, g2)` compares the sorted degree sequences and then the
sorted per-node **triangle-count** sequences of the two graphs. The triangle
count was computed once per graph with the classic O(|V|·d²) string-keyed shape:

```rust
nodes.iter().map(|&node| {
    let mut count = 0;
    if let Some(nbrs) = g.neighbors(node) {                 // Vec<&str> alloc / node
        let nbr_set: HashSet<&str> = nbrs.iter().copied().collect(); // HashSet / node
        for &nbr in &nbrs {
            if let Some(nbr_nbrs) = g.neighbors(nbr) {       // Vec<&str> alloc / neighbour
                for &nn in &nbr_nbrs {
                    if nbr_set.contains(nn) && nn > nbr {     // string hash-probe + string cmp
                        count += 1;
                    }
                }
            }
        }
    }
    count
}).collect()
```

Per node: one `HashSet<&str>` build, one `Vec<&str>` per neighbour, and a string
hash-probe + lexicographic string comparison per candidate — the exact same shape
the `triangles` mark-array lever (br-r37-c1-trimark, 5.54x) fixed, here paid
**twice** (once per graph).

## The lever

Extracted `could_be_isomorphic_triangle_counts(graph)` returning per-node counts
in `nodes_ordered()` order using the proven integer-adjacency + reusable
mark-array kernel:

- one `vec![false; n]` mark array, reused across nodes (reset only the touched bits);
- walk `graph.neighbors_indices(u)` (zero-alloc `&[usize]` slice) instead of
  `graph.neighbors(u)`;
- `O(1)` array probe `in_nbrs[nn]` instead of a `HashSet<&str>` hash-probe;
- integer `nn > nbr` instead of a lexicographic string comparison.

`could_be_isomorphic` now calls it for `g1` and `g2`.

## Byte-identical argument

The triangle count through a node `u` is exactly the number of edges within
`N(u)`. Requiring `nn > nbr` selects each such intra-ego edge **exactly once**
under *any* total order on the endpoints — for any edge `{a, b}` precisely one of
`a > b` / `b > a` holds. Switching the tie-break from lexicographic name order to
integer-index order therefore leaves every per-node count unchanged. The result
is an **integer** count, so there is no floating-point reassociation anywhere.

Verified in-test: on the n=1200, deg=40 graph the mark-array counts are
`assert_eq!`-equal to the string-HashSet baseline
(`could_be_isomorphic_triangle_counts_orig_string`, kept `#[cfg(test)]`). The test
would panic on any mismatch; it passed.

## Median A/B (paired-interleaved, one binary, NULL control)

`cargo test --release -p fnx-algorithms --lib could_be_isomorphic_isotri_ab -- --ignored --nocapture`

Dense pseudo-random ~40-degree graph, n=1200. fnx candidate (mark-array) vs the
preserved string-HashSet baseline, interleaved inside one process, 121 rounds.
Ratio = base/cand, so **>1 means the mark-array kernel is faster**.

| row | median | win_rate | p5_p95 |
|-----|-------:|---------:|--------|
| `MARK_vs_string` | **11.7483x** | 121/121 | [10.0557, 15.6273] |
| `NULL_mark_vs_mark` | 0.9943x | 57/121 | [0.8194, 1.1812] |

The lever median (11.75x) clears the NULL floor by a wide margin: the candidate's
p5 (10.06) is ~8.5x above the NULL p95 (1.18), and every one of 121 paired rounds
won. The win is causal and not measurement drift.

## Gates

- `cargo check -p fnx-algorithms --all-targets` (remote, worker hz2): exit 0, clean.
- Existing `could_be_isomorphic` unit tests: green (see unit_tests.log).
- clippy: see notes (remote `ftui` path-dep worker-availability flake, unrelated
  to this change — optional `ftui-integration` feature is not in fnx-algorithms'
  dependency path).

## Files

- Production: `crates/fnx-algorithms/src/lib.rs` — `could_be_isomorphic` +
  `could_be_isomorphic_triangle_counts`.
- Test-only: `..._orig_string` baseline + `could_be_isomorphic_isotri_ab` A/B.
