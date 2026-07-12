# br-r37-c1-fulljoinbatch — full_join cross-edge batch-insert

Status: **SHIP.** 8.66x, byte-identical. My change clippy-clean (crate has pre-existing peer lint debt,
untouched).

## The target

`full_join(g1, g2)` (fnx-algorithms) — the graph join: copies both operands' nodes and edges, then adds a
cross edge `(u, v)` for **every** `u ∈ V1, v ∈ V2`. Three per-edge insertion phases: g1 edges
(`add_edge_with_attrs`), g2 edges (`add_edge_with_attrs`), and the `O(|V1|·|V2|)` cross-edge block
(`add_edge`). The cross-edge block dominates.

## The lever

Collect all three phases into one `Vec<(String, String, AttrMap)>` (g1 edges, g2 edges, then cross edges
with an empty `AttrMap`) and insert with one `Graph::extend_edges_with_attrs_unrecorded`.

## Byte-identical argument

The loop reads only the **inputs** (never `result`). `extend_edges_with_attrs_unrecorded` canonicalizes,
dedups on the canonical endpoint pair, and merges attrs via the same `existing.extend(attrs)` as
`add_edge_with_attrs`; `add_edge(u,v)` is exactly `add_edge_with_attrs(u,v, AttrMap::new())`, and merging an
empty AttrMap into an existing edge is a no-op — so the cross edges behave identically. Same insertion order
(g1 edges → g2 edges → cross edges). All nodes are pre-added, so every endpoint resolves to an existing
index. Verified: A/B parity `assert_eq!(edges_ordered_borrowed + nodes_ordered)` on two disjoint 100-node
cycle graphs (10200 result edges) passed before timing; suite tests `test_full_join_empty` +
`test_full_join_cross_edges` pass.

## Why this clears the null

Output ≈ `|E1| + |E2| + |V1|·|V2|` — strongly expanding (the cross-edge block alone is 10000 inserts for two
100-node graphs), so the per-edge policy-drop is nearly the entire cost. Textbook "output ≫ |E|" win.

## Median A/B (paired-interleaved, one binary, NULL control)

`cargo test --release -p fnx-algorithms --lib full_join_batch_ab -- --ignored --nocapture`

Two disjoint 100-node cycle graphs (`a0..a99`, `b0..b99`); full_join = 100 + 100 + 10000 = 10200 edges.
61 rounds. Ratio = base/cand, **>1 = batch faster**.

| row | median | win_rate | p5_p95 |
|-----|-------:|---------:|--------|
| `BATCH_vs_string` | **8.6553x** | 61/61 | [6.4055, 12.2860] |
| `NULL_batch_vs_batch` | 0.9951x | 30/61 | [0.9073, 1.1185] |

Decisive: candidate p5 (6.41) ~5.7x above the NULL p95 (1.12); all 61 rounds won.

## Clippy note

My change is clippy-clean (0 findings in production ~39513-39534 / test ~68185-68314, grep-verified). The
crate has 12 pre-existing clippy `-D warnings` errors in peer/committed code — left untouched per
shared-checkout discipline.

## Files

- Production: `crates/fnx-algorithms/src/lib.rs` — `full_join`.
- Test-only: `full_join_batch_ab` A/B.

## Vein status

Seventeenth result-builder batch win. The expanding-builder family continues to pay: `full_join`'s
cross-product block is the largest single "output ≫ |E|" surface after moral_graph's dup pile-up. Next:
remaining expanding builders (`transitive_closure` if the kernel is reached; `make_clique_bipartite`).
