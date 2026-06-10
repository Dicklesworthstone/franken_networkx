# perf(_materialize_filtered_view): batch construction

br-r37-c1-35b3i

## Problem
`_materialize_filtered_view` builds a concrete fnx graph holding a
SubgraphView's visible nodes + edges so callers that hand the result to Rust
`_raw_*` operators see the filtered contents. It is coerced from **every**
SubgraphView (via `_coerce_arg_to_fnx_graph`), so it is on the hot path of every
algorithm called on `G.subgraph(...)` / `edge_subgraph(...)`. It built the graph
with a **per-node `add_node` + per-edge `add_edge` loop** — each a separate PyO3
crossing — at **3.4 ms (210n/1.1k e) → 13 ms (700n/4.9k e)**.

## Lever (one)
Assemble with **batch** `add_nodes_from` / `add_edges_from` (the at-parity
construction fast path): `add_nodes_from((n, dict(d)) for n,d in
view.nodes(data=True))` + `add_edges_from((u,v,dict(d)) ...)` (4-tuple form for
multigraphs). The view's node + edge iteration order is preserved, so the
materialized graph is byte-identical — only the build path changes. Python-only.

Touched: `python/franken_networkx/__init__.py` (`_materialize_filtered_view`).

## Proof (nx-exact)
`harness_proof.py`: 21 cases — Graph / DiGraph / MultiGraph / MultiDiGraph × 5
seeds (node-induced subgraph views) + an edge_subgraph view. The materialized
graph **== the source view** (nodes+attrs, edges+attrs incl. keys, graph dict,
directed/multigraph flags) — 0 mismatches. Edge-attr identity (`M[u][v] is
M[u][v]`) + post-hoc mutation verified.
Fingerprint sha256: `3b064259b00519119901676ae9c49674663b309dd234c0c2ef73fc679677693b`
pytest -k "subgraph/view/filtered/coerce": **2366 passed** (2 unrelated
pre-existing `53wz7` iteration-mutation failures, identical on baseline).

## Timing (warm min-of-6, fresh-view materialization, gnp 0.7-node-induced subgraph)
| source n | view (n/e) | baseline | new | self-speedup |
|----------|-----------:|---------:|----:|-------------:|
| 300  | 210 / 1113 | 3.61 ms | 2.46 ms | 1.47× |
| 600  | 420 / 2707 | 8.21 ms | 4.24 ms | 1.94× |
| 1000 | 700 / 4940 | 12.73 ms | 7.57 ms | 1.68× |

1.47–1.94× self-speedup, growing with edge count; cascades to every algorithm
called on a filtered view.

## Score
Impact: high (1.47–1.94× on a broadly-cascading view-coercion helper).
Confidence: high (byte-identical materialization across all 4 graph types +
edge_subgraph + identity/mutation, 2366 tests). Effort: very low (per-edge loop
-> batched, Python-only). Score >> 2.0.
