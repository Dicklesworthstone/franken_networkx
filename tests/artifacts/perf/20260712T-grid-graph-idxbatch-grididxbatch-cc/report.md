# br-r37-c1-grididxbatch — grid_graph (n-dim) upgraded to the INDEX batch

Status: **SHIP.** 12.69x (up from the earlier 2.73x String-pair batch on the same graph), byte-identical
across 1D/2D/3D/4D. My change clippy-clean (crate has pre-existing peer lint debt, untouched).

## The target

`grid_graph(dim)` (fnx-algorithms) — the n-dimensional grid. Earlier this session it got a **String-pair**
batch (`br-r37-c1-gridbatch`, 2.73x) that still built two `coords_to_label` String labels per edge. This
lever upgrades it to the **index batch**, eliminating those per-edge label allocs.

## The lever — index-computable labels

Nodes are added in flat-index order, so node `i` sits at index `i`. The `+1`-in-dimension-`d` neighbour of
flat index `i` is `i + strides[d]`, where `strides[d] = product(dim[d+1..])` (the inverse of the row-major
`index_to_coords`, which fills `coords[k] = index % dim[k]` from the last dimension). So the edges collect as
`(i, i + strides[d])` **usize index pairs** + one `Graph::extend_existing_index_edges_unrecorded` — needing
**no labels** (only the boundary check `coords[d]+1 < dim[d]` still decodes `coords`). Node build → one
`extend_nodes_unrecorded` over the `coords_to_label` labels. This is the same "string label whose index is
computable from the loop vars → 12x tier not 2.7x tier" lever proven on `grid_2d_graph`.

## Byte-identical argument

Adding 1 to `coords[d]` (guarded by `coords[d]+1 < dim[d]`, so no carry) adds exactly `strides[d]` to the
flat index, and `index_to_coords(i + strides[d]) = neighbor_coords`, so node `i + strides[d]` is precisely
`coords_to_label(neighbor_coords)` — the identical edge endpoint as the original. Every edge has
`source < target`; the helper canonicalizes `edge_index_endpoints` by node **name** (identical string
comparison to `add_edge`) and pushes `adj_indices` in the same i-major/dimension order.
`extend_nodes_unrecorded` preserves the flat-index→label map. Verified: A/B parity `assert_eq!
(edges_ordered_borrowed + nodes_ordered)` on dim `[100,100]` **plus n-dim stride-correctness probes** `[7]`
(1D), `[4,5,6]` (3D irregular), `[3,2,4,3]` (4D irregular) — all byte-identical to the per-edge
`coords_to_label` baseline. (grid_graph has no dedicated Rust suite test; byte-identity rests on this A/B
parity + the Python differential tests `tests/python/test_lattice_generators.py`.)

## Median A/B (paired-interleaved, one binary, NULL control)

`cargo test --release -p fnx-algorithms --lib grid_graph_idxbatch_ab -- --ignored --nocapture`

grid_graph(`[100,100]`): 10000 nodes, 19800 edges. 61 rounds. Ratio = base/cand (base = the ORIGINAL per-edge
coords_to_label build), **>1 = batch faster**.

| row | median | win_rate | p5_p95 |
|-----|-------:|---------:|--------|
| `BATCH_vs_string` | **12.6885x** | 61/61 | [10.3408, 15.3132] |
| `NULL_batch_vs_batch` | 1.0159x | 38/61 | [0.8168, 1.2459] |

Decisive: candidate p5 (10.34) ~8.3x above the NULL p95 (1.25); all 61 rounds won. This is a **4.6x upgrade**
over the earlier `br-r37-c1-gridbatch` String-pair batch (2.73x on the identical 100×100 grid).

## Clippy note

My change is clippy-clean (0 findings in production ~34073-34098 / test ~70053-70200, grep-verified). The
crate has 12 pre-existing clippy `-D warnings` errors in peer/committed code — left untouched per
shared-checkout discipline.

## Files

- Production: `crates/fnx-algorithms/src/lib.rs` — `grid_graph`.
- Test-only: `grid_graph_idxbatch_ab` A/B.

## Vein status

Thirty-third result-builder batch win. Applies the `grid_2d_graph` "index-computable string label" lever to
the n-dimensional case (with stride arithmetic). The grid family is now fully on the index-batch tier.
