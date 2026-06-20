# BOLD-VERIFY session scorecard — CopperCliff (cc) — 2026-06-20

Measured head-to-head vs NetworkX (warm, min-of-N / interleaved). Pure-Python
lane (no peer Rust crates touched).

## Shipped wins (4 commits, main+master)

| fn | variants | before | after | commit |
|----|----------|--------|-------|--------|
| `node_degree_xy` | undir / dir whole-graph | 0.113x / 0.231x | **4.43x / 3.43x** | 3dd80d3ad |
| `average_degree_connectivity` | all dir + weighted | 0.013x–0.26x | **1.05x–2.49x** | 543b9d9bf |
| `average_neighbor_degree` | weighted (4 variants) | 0.47x–0.57x | **0.77x–1.31x** (3/4 ≥1.0) | e22d53874 |
| `to_numpy_array` / `to_scipy_sparse_array` / `adjacency_matrix` | Multi(Di)Graph weighted | 0.39x–0.56x | **0.58x–1.00x** (loss→parity) | 855a4a705 |

Two levers:
1. **Per-node-view substrate tax** (assortativity family): pure-Python algos that
   walk fnx VIEWS (DegreeView/EdgeView/AtlasView) per node pay a tax nx avoids
   with dict walks. Replace with bulk degree dicts + one native adjacency snapshot
   (`_native_adjacency_keys`/`_native_adjacency_dict`) or a `to_scipy` mat-vec.
   Per-bucket-sum results are order-invariant.
2. **Unused native kernel reroute** (multigraph matrices): a native COO kernel
   (`adjacency_arrays_multigraph`) existed but was gated out of the default call —
   admit it (guarded by the non-finite/non-numeric scan).

All proven byte/value-exact: node_degree_xy 192, adc 1500, anb 2000, multigraph
matrices 320 — **0 fails**, golden shas in each artifact dir. Conformance green
(family suites pass; pre-existing unrelated `node_connectivity` Menger failures
confirmed failing on clean HEAD).

## Negative evidence — losses found, NOT pure-Python-closable (filed as beads)

| fn | variant | ratio | root cause | bead |
|----|---------|-------|------------|------|
| `to_*` matrix exporters | MultiDiGraph residual | 0.58–0.69x | native `_sync_rust_edge_attrs` 2.5ms for MDG (no dirty-flag) + `adjacency_arrays_multigraph` stringifies every node | br-r37-c1-iyu0a (P3) |
| `reverse(copy=True)` | MultiDiGraph | 0.43x | native kernel substrate; DiGraph integer-space `reversed()` not ported to MDG | br-r37-c1-nooou |
| `pagerank` | MultiDiGraph weighted | 0.60x | multigraph `to_scipy` substrate | (iyu0a) |
| `average_neighbor_degree` | dir out/in weighted | 0.77x | residual: weighted `to_scipy` construction ≈ nx total (= br-r37-c1-wvuf7) | wvuf7 |

| `get_edge_attributes` | Graph weighted | 0.50x | EdgeView substrate; native kernel lossy (`val.as_str()`), `edge_py_attrs` lazily materialized so a typed Python-dict kernel would miss bulk-built attrs | br-r37-c1-w868y |
| `ramsey_R2`, `treewidth_*` (approx) | undirected | 0.75–0.81x | set-iteration-order-dependent → must stay delegated (conversion tax) | — |

These need native Rust kernels (fnx-python/fnx-classes crates), out of the
pure-Python lane. The pure-Python reroute already converted the multigraph
matrix-exporter losses (0.39–0.56x) to near-parity/win (shipped 855a4a705).

### Diagnosis depth (this pass)

Traced the MDG matrix residual to a precise 1-method Rust fix
(`_fnx_sync_edge_attrs_to_inner` on PyMultiDiGraph — MDG `add_edge` populates
`node_py_attrs` so the full sync's unconditional node walk costs 2.5ms; MG is
free) — **handed to CrimsonRiver** (digraph.rs is their exclusive lock) with the
exact patch in bead iyu0a + mail. Verified `get_edge_attributes` is genuinely
substrate-bound (native kernel lossy; `edge_py_attrs` lazy) rather than a missed
reroute. Swept ~135 functions total across assortativity, distance, centrality,
clustering, similarity, operators, generators, flow, tree, spectral, IO,
matrix, small-input/multigraph, and the approximation namespace.

## Neutral / already-winning (sampled, no action)

Swept ~55 functions across distance, centrality, clustering, similarity, matrix
IO, community. fnx already WINS almost everywhere — representative: closeness
131x, harmonic 170x, katz 313x, second_order 2984x, eccentricity/diameter/center
13–18x, betweenness(MG) 14x, average_clustering 54x, transitivity 98x. Washes
(~1.0x): `hits`, `simrank_similarity`, `panther_similarity`, `node_clique_number`,
`to_dict_of_dicts[MG]`. No regressions introduced.
