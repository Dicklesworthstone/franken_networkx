# br-r37-c1-modwborrow — modularity w_map build: `edges_ordered()` → `edges_ordered_borrowed()`

Status: **SHIP (modest).** 1.3424x on the w_map-build loop, byte-identical. Member of the
`redundant_edge_materialization` family (owned→borrowed flavor). Follows my br-r37-c1-modwmap on the same fn.

## The target

`modularity`'s edge loop builds the index-keyed weight map `w_map` by scanning every edge. It iterated
`graph.edges_ordered()`, which materialises a `Vec<EdgeSnapshot>` — **two owned-String clones + an AttrMap
clone per edge**. But the loop only reads the endpoint NAMES (a `node_to_idx` probe + an
`edge_weight_or_default` re-lookup) and never keeps the owned Strings or reads `edge.attrs`. The per-edge
clone is pure waste.

## The lever

`edges_ordered_borrowed()` does the identical internal pair-walk but yields `(&str, &str, &AttrMap)` — **zero
per-edge allocation** (see `fnx-classes` `edges_ordered_borrowed` vs `edges_ordered`: the only difference is
`name.clone()`×2 + `attrs.clone()` vs pointer copies). Swap the loop to it and index `node_to_idx[left]`
directly.

## Byte-identical argument

`edges_ordered_borrowed()` walks the same order-faithful adjacency mirror and yields the same unique edges in
the same order with the same node names (just borrowed). The loop body is unchanged apart from reading
`left`/`right` as `&str` directly instead of `edge.left.as_str()`. So `w_map` is populated with the identical
(canonical-pair → weight) entries → the downstream `q` sum is ULP-identical. Verified: the A/B asserts
`old_fn() == new_fn()` (exact `HashMap<(usize,usize),f64>` equality) before timing; the production
`modularity_perfect_partition` (Q value) + 7 more modularity/greedy_modularity suite tests pass.

## Median A/B (isolated loop, paired-interleaved, one binary, NULL control)

`cargo test --release -p fnx-algorithms --lib modularity_wmap_borrow_ab -- --ignored --nocapture`

Times ONLY the changed w_map-build loop (its exact self-time) on a dense graph (8k nodes, ~200k edges) so
the per-edge clone is the dominant cost. 61 rounds. Ratio = owned / borrowed, **>1 = borrowed faster**.

| row | median | win_rate | p5_p95 |
|-----|-------:|---------:|--------|
| `BORROWED_vs_owned` | **1.3424x** | 61/61 | [1.0924, 1.6395] |
| `NULL_borrowed_vs_borrowed` | 1.0139x | 32/61 | [0.8640, 1.2892] |

**MODEST — gated on median>null-p95 + decisive sign test, NOT strict p5>p95.** Median (1.342) clears null
p95 (1.289); sign test 61/61 vs null 32/61 (null cleanly centred ~1.0). Candidate p5 (1.092) overlaps the
null p95 (1.289) because the per-edge `edge_weight_or_default` graph re-lookup (common to both arms) dilutes
the clone-saving fraction. Same shipping bar as sibling `greedy_modularity` (1.15x, gmodmat) and `modularity`
(1.71x, modmat). Scaled from 4k/60k (1.43x, wider null p95 1.30) → 8k/200k per the family sizing lesson to
re-centre the null. The change is bit-identical AND strictly-better (removing clones can never regress), so
there is no downside even at the modest margin.

## Files

- Production: `crates/fnx-algorithms/src/lib.rs` — `modularity` w_map-build loop.
- Test-only: `modularity_wmap_borrow_ab` A/B.

## Vein status

`edges_ordered()` (owned) → `edges_ordered_borrowed()` (borrowed) wherever the loop only reads names/attrs by
ref and never keeps the owned data. Other candidate sites still on owned iteration that only borrow:
`is_isomorphic`/`is_isomorphic_directed` adjacency build (VF2-diluted), `number_of_spanning_arborescences`
(determinant-diluted), `to_prufer_sequence`. Operators that MOVE the data into a result graph (graph_union
etc.) legitimately need owned — skip.
