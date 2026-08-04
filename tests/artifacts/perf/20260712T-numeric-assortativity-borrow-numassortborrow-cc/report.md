# br-r37-c1-numassortborrow — numeric_assortativity_coefficient: `edges_ordered()` → `edges_ordered_borrowed()`

Status: **SHIP.** 1.6409x, byte-identical, clears the STRICT p5>null-p95 gate. Member of the
`redundant_edge_materialization` family (owned→borrowed flavor). The clean, undiluted counterpart to the
map-insert-heavy `attribute_mixing_dict` (modest 1.38x).

## The target

`numeric_assortativity_coefficient(graph, attribute)` computes the Pearson correlation of a scalar node
attribute across edges (Newman 2003). Its mixing-matrix build is a pure O(E) edge scan: per edge, two
`node_attrs` lookups → a `u64` bit-pattern → a `val_idx` `HashMap<u64,usize>` probe → two `counts[][] += 1`
array increments. It iterated `graph.edges_ordered()`, which materialises a `Vec<EdgeSnapshot>` — **two
owned-String clones + an AttrMap clone per edge** — even though the loop only reads the endpoint NAMES.

## The lever

`edges_ordered_borrowed()` yields `(&str, &str, &AttrMap)` — **zero per-edge allocation**. Pass `left`/`right`
(`&str`) to `node_attrs`. Because the remaining per-edge work is CHEAP (a `u64` hash probe + array writes, no
String map inserts, no allocation), the removed edge-snapshot clone is an **undiluted** fraction — hence the
clean strict-gate win vs the map-insert-diluted `attribute_mixing_dict`.

## Byte-identical argument

Same unique edges, same walk order, same node names (just borrowed); `node_attrs`/`as_f64`/`to_bits`, the
`val_idx` probe and the `counts` increments are unchanged. The coefficient is a single f64 derived from the
integer `counts` matrix (order-independent accumulation) → ULP-identical. Verified: the A/B asserts
`old_fn(&g) == new_fn(&g)` (exact `Vec<Vec<usize>>` counts-matrix equality, owned vs borrowed) on a 400k-edge
attributed graph before timing.

## Median A/B (changed loop, paired-interleaved, one binary, NULL control)

`cargo test --release -p fnx-algorithms --lib numeric_assort_borrow_ab -- --ignored --nocapture`

Isolated owned→borrowed (BOTH arms do the identical node_attrs lookups + u64 probe + counts increments).
Graph: 10k nodes with a 5-value `val` Int attribute, ~400k edges. 61 rounds. Ratio = owned / borrowed,
**>1 = borrowed faster**.

| row | median | win_rate | p5_p95 |
|-----|-------:|---------:|--------|
| `BORROWED_vs_owned` | **1.6409x** | 61/61 | [1.4221, 1.8744] |
| `NULL_borrowed_vs_borrowed` | 0.9896x | 29/61 | [0.8058, 1.1471] |

Decisive: candidate **p5 (1.422) is well above the null p95 (1.147)** — clears the STRICT gate (like
node_degree_xy 1.49x / _directed 2.71x, unlike the map-heavy attribute_mixing 1.38x / modularity 1.34x which
only cleared median>p95). All 61 rounds won; null cleanly centred on 1.0.

## Files

- Production: `crates/fnx-algorithms/src/lib.rs` — `numeric_assortativity_coefficient`.
- Test-only: `numeric_assort_borrow_ab` A/B.

## Vein status

owned→borrowed now 5 wins. MAGNITUDE RULE reconfirmed: the strict-gate wins (node_degree_xy family,
numeric_assortativity) all have CHEAP per-edge work (degree/index lookups + array writes); the modest ones
(attribute_mixing, modularity) pay a heavy per-edge op (String map insert / weight re-lookup) that dilutes the
clone saving and inflates the null. Sweep remaining pure-O(E), cheap-per-edge, name-only edge scans; skip
result-graph builders (move data) and algorithm-dominated loops (Amdahl).
