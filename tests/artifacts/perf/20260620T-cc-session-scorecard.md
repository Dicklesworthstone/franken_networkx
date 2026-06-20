# BOLD-VERIFY session scorecard — CopperCliff (cc) — 2026-06-20

Measured head-to-head vs NetworkX (warm, min-of-N / interleaved). Pure-Python
lane (no peer Rust crates touched).

## Shipped wins (3 commits, main+master)

| fn | variants | before | after | commit |
|----|----------|--------|-------|--------|
| `node_degree_xy` | undir / dir whole-graph | 0.113x / 0.231x | **4.43x / 3.43x** | 3dd80d3ad |
| `average_degree_connectivity` | all dir + weighted | 0.013x–0.26x | **1.05x–2.49x** | 543b9d9bf |
| `average_neighbor_degree` | weighted (4 variants) | 0.47x–0.57x | **0.77x–1.31x** (3/4 ≥1.0) | e22d53874 |

Common lever: pure-Python algos that walk per-node fnx VIEWS (DegreeView /
EdgeView / AtlasView) pay a substrate tax nx avoids with dict walks. Replace with
bulk degree dicts + one native adjacency snapshot (`_native_adjacency_keys` /
`_native_adjacency_dict`) or a `to_scipy` mat-vec. Per-bucket-sum results are
order-invariant. All proven byte/value-exact: node_degree_xy 192 checks, adc 1500,
anb 2000 — **0 fails**, golden shas in each artifact dir. Conformance green
(family suites pass; pre-existing unrelated `node_connectivity` Menger failures
confirmed failing on clean HEAD).

## Negative evidence — losses found, NOT pure-Python-closable (filed as beads)

| fn | variant | ratio | root cause | bead |
|----|---------|-------|------------|------|
| `to_numpy_array` / `to_scipy_sparse_array` | MultiGraph weighted | 0.47x | no native multigraph COO kernel; `to_scipy.toarray` (3.2ms) & `_native_adjacency_dict` (3.8ms) BOTH slower than nx (1.8ms) — fnx multigraph edge-iteration substrate | br-r37-c1-iyu0a |
| `pagerank` | MultiDiGraph weighted | 0.60x | same multigraph `to_scipy` substrate | (iyu0a) |
| `average_neighbor_degree` | dir out/in weighted | 0.77x | residual: weighted `to_scipy` construction ≈ nx total (= br-r37-c1-wvuf7) | wvuf7 |

These need native Rust COO/degree-pair kernels (fnx-convert/fnx-python crates),
out of the pure-Python lane.

## Neutral / already-winning (sampled, no action)

Swept ~55 functions across distance, centrality, clustering, similarity, matrix
IO, community. fnx already WINS almost everywhere — representative: closeness
131x, harmonic 170x, katz 313x, second_order 2984x, eccentricity/diameter/center
13–18x, betweenness(MG) 14x, average_clustering 54x, transitivity 98x. Washes
(~1.0x): `hits`, `simrank_similarity`, `panther_similarity`, `node_clique_number`,
`to_dict_of_dicts[MG]`. No regressions introduced.
