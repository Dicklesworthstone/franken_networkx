# br-r37-c1-ndxydirborrow — node_degree_xy_directed: `edges_ordered()` → `edges_ordered_borrowed()`

Status: **SHIP.** 2.7072x, byte-identical. Directed twin of br-r37-c1-ndxyborrow; member of the
`redundant_edge_materialization` family (owned→borrowed flavor). Clears the STRICT p5>null-p95 gate.

## The target

`node_degree_xy_directed(digraph, x_type, y_type)` returns `Vec<(usize, usize)>` — the degree pair for every
directed edge — the directed degree-correlation input for the assortativity/degree-mixing coefficients. A
**pure O(E) loop**: for each edge, two O(1) `in_degree`/`neighbor_count` lookups (per the x_type/y_type arms)
and a push. It iterated `digraph.edges_ordered()`, which materialises a `Vec<EdgeSnapshot>` — **two owned-
String clones + an AttrMap clone per edge** — even though the loop only reads the endpoint NAMES.

## The lever

`edges_ordered_borrowed()` (DiGraph, `fnx-classes/src/digraph.rs:1651`) runs the identical internal pair-walk
but yields `(&str, &str, &AttrMap)` — **zero per-edge allocation**. Pass `left`/`right` (`&str`) straight to
`in_degree`/`neighbor_count`.

## Byte-identical argument

Same unique edges, same walk order, same node names (just borrowed); `in_degree`/`neighbor_count` unchanged.
So each `(du, dv)` pair — and its order — is identical. Verified: the A/B asserts `old_fn(&g) == new_fn(&g)`
(exact `Vec<(usize,usize)>` equality, owned vs borrowed, both using in_degree/neighbor_count) on a 200k-edge
directed graph before timing; the `degree_mixing` suite (which consumes `node_degree_xy_directed` via
`test_degree_mixing_dict_directed_uses_out_in_degrees`) is byte-identical by construction.

## Median A/B (whole function, paired-interleaved, one binary, NULL control)

`cargo test --release -p fnx-algorithms --lib node_degree_xy_directed_borrow_ab -- --ignored --nocapture`

Isolated owned→borrowed (BOTH arms use in_degree/neighbor_count; x_type=y_type="both"). Dense directed
circulant (8k nodes, out-degree 25 → ~200k directed edges). 61 rounds. Ratio = owned / borrowed, **>1 =
borrowed faster**.

| row | median | win_rate | p5_p95 |
|-----|-------:|---------:|--------|
| `BORROWED_vs_owned` | **2.7072x** | 61/61 | [2.3458, 3.3137] |
| `NULL_borrowed_vs_borrowed` | 0.9934x | 27/61 | [0.8272, 1.2600] |

Decisive: candidate **p5 (2.346) is ~1.9x above the null p95 (1.260)** — clears the STRICT p5>null-p95 gate
(unlike the undirected twin 1.49x / modularity 1.34x which only cleared median>p95). All 61 rounds won; null
centred on 1.0. Larger than the undirected twin because the DiGraph `edges_ordered()` snapshot clone is a
bigger fraction here relative to the (cheap) degree lookups.

## Files

- Production: `crates/fnx-algorithms/src/lib.rs` — `node_degree_xy_directed`.
- Test-only: `node_degree_xy_directed_borrow_ab` A/B.

## Vein status

owned→borrowed now has 3 wins (node_degree_xy 1.49x, node_degree_xy_directed 2.71x, modularity 1.34x). Best
targets = pure-O(E) name-only transforms. Sweep the remaining `for edge in <g>.edges_ordered()` (owned) sites
whose bodies only borrow (many under fnx-algorithms) — but skip operators that MOVE edge data into a result
graph and heavy-per-edge or algorithm-dominated loops (diluted).
