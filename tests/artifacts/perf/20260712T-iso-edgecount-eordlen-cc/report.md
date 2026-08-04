# br-r37-c1-eordlen — isomorphism/planarity edge count: `edges_ordered().len()` → `edge_count()`

Status: **SHIP.** 35.19x on `faster_could_be_isomorphic`, byte-identical. Member of the
`redundant_edge_materialization` family.

## The target

Seven quick-reject comparison / planarity functions counted edges with `g.edges_ordered().len()`.
`edges_ordered()` materialises a full `Vec<EdgeSnapshot>` — **two owned-String clones plus an AttrMap
clone PER EDGE** (see `fnx-classes` `edges_ordered`) — and the whole Vec is dropped after reading `.len()`.
`edge_count()` is `self.edges.len()` — O(1), no allocation.

Sites converted (all simple `Graph`/`DiGraph`, so bit-identical — see below):

- `is_isomorphic` (×2), `is_isomorphic_directed` (×2)
- `could_be_isomorphic` (×2)
- `faster_could_be_isomorphic`, `faster_could_be_isomorphic_directed`, `fast_could_be_isomorphic`
- `is_planar` (the `m = |E|` for the `|E| ≤ 3|V|−6` Euler bound)

(The two `write_graphml_*` buffer-size *estimates* also use `edges_ordered().len()`; left for a trivial
follow-up — different function family, I/O-path, low Amdahl value.)

## Byte-identical argument

`edge_count()` returns `self.edges.len()`. `edges_ordered()` walks the order-faithful adjacency mirror and
pushes exactly one `EdgeSnapshot` per unique canonical edge pair (deduped via `seen.insert(pair)`), so its
length equals the number of stored edges == `edge_count()`. All converted sites are simple `Graph`/`DiGraph`
(no parallel edges), so there is no multi-edge discrepancy. The existing code already treated
`edges_ordered().len()` AS the edge count for its isomorphism/planarity rejection, so the value is unchanged;
only the wasted materialisation is removed. Verified: the A/B asserts `old_fn == new_fn` (full
`faster_could_be_isomorphic`, `edges_ordered().len()` vs `edge_count()`) before timing.

## Median A/B (paired-interleaved, one binary, NULL control)

`cargo test --release -p fnx-algorithms --lib faster_could_be_iso_eordlen_ab -- --ignored --nocapture`

Two equal-order **and** equal-size graphs (10k nodes, ~100k edges each) so BOTH arms pass the node and edge
checks and run the *whole* function (edge count + degree sort) — the wasted edge Vec is the dominant
self-time. 61 rounds. Ratio = edges_ordered().len() / edge_count(), **>1 = edge_count faster**.

| row | median | win_rate | p5_p95 |
|-----|-------:|---------:|--------|
| `EDGECOUNT_vs_edgesordered` | **35.1888x** | 61/61 | [29.2128, 66.7683] |
| `NULL_edgecount_vs_edgecount` | 0.9971x | 29/61 | [0.7985, 1.1598] |

Decisive: candidate p5 (29.21) is ~25x above the NULL p95 (1.16); all 61 rounds won; NULL centred on 1.0.
(On the node-match / edge-count-mismatch early-reject path, this materialisation is ~100% of the function's
self-time.)

## Files

- Production: `crates/fnx-algorithms/src/lib.rs` — 7 functions, 10 sites.
- Test-only: `faster_could_be_iso_eordlen_ab` A/B.

## Vein status

`redundant_edge_materialization` family: `edges_ordered().len()` is never the right way to count edges —
`edge_count()` is O(1). Remaining known sites: the two `write_graphml_*` size estimates (46456, 46671).
