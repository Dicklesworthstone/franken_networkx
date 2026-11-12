# br-r37-c1-ndxyborrow — node_degree_xy: `edges_ordered()` → `edges_ordered_borrowed()`

Status: **SHIP.** 1.4874x, byte-identical. Member of the `redundant_edge_materialization` family
(owned→borrowed flavor). Cleaner than the sibling `modularity` modwborrow (1.34x) — less per-edge dilution.

## The target

`node_degree_xy(graph)` returns `Vec<(usize, usize)>` — the `(deg(u), deg(v))` pair for every edge — the
degree-correlation input for the assortativity coefficients. It is a **pure O(E) loop**: for each edge, two
O(1) `neighbor_count` probes and a push. It iterated `graph.edges_ordered()`, which materialises a
`Vec<EdgeSnapshot>` — **two owned-String clones + an AttrMap clone per edge** — even though the loop only
reads the endpoint NAMES and never keeps the owned data. Because the only other per-edge work is two cheap
probes, the clone is a large fraction of the loop, so removing it moves the needle more than it did in
modularity (whose `edge_weight_or_default` re-lookup diluted the clone fraction).

## The lever

`edges_ordered_borrowed()` runs the identical internal pair-walk but yields `(&str, &str, &AttrMap)` — **zero
per-edge allocation**. Swap the loop to it and pass `left`/`right` (`&str`) straight to `neighbor_count`.

## Byte-identical argument

`edges_ordered_borrowed()` yields the same unique edges in the same walk order with the same node names (just
borrowed). `neighbor_count(name)` is unchanged. So each `(du, dv)` pair — and their order — is identical.
Verified: the A/B asserts `old_fn(&g) == new_fn(&g)` (exact `Vec<(usize,usize)>` equality, owned vs borrowed,
both using `neighbor_count`) on a 200k-edge graph before timing; the assortativity suite (which consumes
`node_degree_xy`) passes.

## Median A/B (whole function, paired-interleaved, one binary, NULL control)

`cargo test --release -p fnx-algorithms --lib node_degree_xy_borrow_ab -- --ignored --nocapture`

Isolated from the ra004 `neighbor_count` lever — BOTH arms use `neighbor_count`; they differ ONLY in owned
vs borrowed edge iteration. Dense circulant (8k nodes, degree 50 → ~200k edges) so the edge scan is the whole
function. 61 rounds. Ratio = owned / borrowed, **>1 = borrowed faster**.

| row | median | win_rate | p5_p95 |
|-----|-------:|---------:|--------|
| `BORROWED_vs_owned` | **1.4874x** | 61/61 | [1.1606, 1.7242] |
| `NULL_borrowed_vs_borrowed` | 1.0099x | 35/61 | [0.8727, 1.2207] |

Median (1.487) clears the null p95 (1.221) with a solid margin; sign test 61/61 vs null 35/61; null cleanly
centred on 1.0. (Candidate p5 1.161 sits just under the null p95 1.221 — a slight tail overlap — but the
central tendencies are well separated. Bit-identical + strictly-better, so no downside.)

## Files

- Production: `crates/fnx-algorithms/src/lib.rs` — `node_degree_xy`.
- Test-only: `node_degree_xy_borrow_ab` A/B.

## Vein status

`edges_ordered()` (owned) → `edges_ordered_borrowed()` (borrowed) wherever the loop only reads names/attrs by
ref. Best targets are pure-O(E) transforms where the clone isn't diluted by heavy per-edge work (node_degree_xy
= ideal; modularity = diluted by the weight re-lookup; is_isomorphic = diluted by VF2). Directed twin
`node_degree_xy_directed` (40406) is the natural next candidate — same shape.
