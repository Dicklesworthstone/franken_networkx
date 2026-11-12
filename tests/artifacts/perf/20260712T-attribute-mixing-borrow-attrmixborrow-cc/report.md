# br-r37-c1-attrmixborrow — attribute_mixing_dict: `edges_ordered()` → `edges_ordered_borrowed()`

Status: **SHIP (modest).** 1.3755x, byte-identical. Member of the `redundant_edge_materialization` family
(owned→borrowed flavor); attribute analog of the node_degree_xy borrow wins. Same tier as the shipped
`modularity` modwborrow (1.34x).

## The target

`attribute_mixing_dict(graph, attribute)` builds the `(u_attr, v_attr) → count` mixing map that feeds
`attribute_assortativity`. A pure O(E) edge scan: for each edge, two `node_attrs` lookups + one/two count
inserts. It iterated `graph.edges_ordered()`, which materialises a `Vec<EdgeSnapshot>` — **two owned-String
clones + an AttrMap clone per edge** — even though the loop only reads the endpoint NAMES (`node_attrs`
lookups + the `left != right` self-loop test) and never keeps the owned edge data.

## The lever

`edges_ordered_borrowed()` yields `(&str, &str, &AttrMap)` — **zero per-edge allocation**. Pass `left`/`right`
(`&str`) to `node_attrs` and compare them for the self-loop branch.

## Byte-identical argument

Same unique edges, same walk order, same node names (just borrowed); `node_attrs`/`get`/`as_str` and the
`(u_val, v_val)` count inserts are unchanged. So the mixing map is identical. Verified: the A/B asserts
`old_fn(&g) == new_fn(&g)` (exact `HashMap<(String,String),usize>` equality, owned vs borrowed) on a 400k-edge
attributed graph before timing.

## Median A/B (whole function, paired-interleaved, one binary, NULL control)

`cargo test --release -p fnx-algorithms --lib attribute_mixing_dict_borrow_ab -- --ignored --nocapture`

Isolated owned→borrowed (BOTH arms do the identical node_attrs lookups + inserts). Graph: 10k nodes with a
5-value `color` attribute, ~400k edges. 61 rounds. Ratio = owned / borrowed, **>1 = borrowed faster**.

| row | median | win_rate | p5_p95 |
|-----|-------:|---------:|--------|
| `BORROWED_vs_owned` | **1.3755x** | 59/61 | [1.0553, 1.6682] |
| `NULL_borrowed_vs_borrowed` | 1.0143x | 33/61 | [0.7917, 1.2527] |

**MODEST — gated on median>null-p95 + sign test, NOT strict p5>p95.** Median (1.376) clears null p95 (1.253)
with a 1.10x margin; sign 59/61 vs null 33/61; null cleanly centred (1.014). Candidate p5 (1.055) overlaps the
null p95 (1.253) because the per-edge `(String,String)` map inserts (common to both arms) are allocation-heavy
and dilute the clone-saving fraction + widen the null. Scaled 8k/200k (median 1.457, null p95 1.335, biased
1.039/39-61) → 10k/400k per the sizing lesson to re-centre and tighten the null. Same tier as `modwborrow`;
bit-identical AND strictly-better (removing clones can never regress), so no downside at the margin.

## Files

- Production: `crates/fnx-algorithms/src/lib.rs` — `attribute_mixing_dict`.
- Test-only: `attribute_mixing_dict_borrow_ab` A/B.

## Vein status

owned→borrowed now 4 wins (node_degree_xy 1.49x, node_degree_xy_directed 2.71x, modularity 1.34x,
attribute_mixing_dict 1.38x). Magnitude tracks the UNDILUTED clone fraction: pure name-only degree transforms
(node_degree_xy) win biggest; map-insert-heavy accumulators (attribute_mixing_dict, modularity) are modest.
Skip operators that MOVE edge data into a result graph (relabel_nodes/identified_nodes) — they need owned.
