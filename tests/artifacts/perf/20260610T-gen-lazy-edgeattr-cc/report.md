# perf(directed generators): lazy edge-attr dicts

br-r37-c1-2pzo7

## Problem
`report_to_pydigraph` (the Rust→PyDiGraph converter behind every directed
generator: `fast_gnp_random_graph`, `gn_graph`, `gnr_graph`, `gnc_graph`,
`scale_free_graph` directed) ran a second pass after the fast inner edge
insertion, allocating an empty `PyDict::new(py)` into `edge_py_attrs` **per
edge** (+ an endpoint String tuple each). For dense directed output that's O(E)
wasted PyDict allocs — the same construction tax fixed in `complement`
(br-r37-c1-cqfgt). The undirected `report_to_pygraph` was already lazy.

## Lever (one)
Drop the eager per-edge `edge_py_attrs` loop in `report_to_pydigraph`. PyDiGraph
materialises edge attr dicts lazily (`or_insert_with(PyDict::new)`) on first
`G[u][v]` / `edges(data=True)` / `to_dict_of_dicts` access and stores the result,
so `G[u][v] is G[u][v]` identity holds. Generator output carries no edge data, so
this is byte-identical.

**MultiDiGraph keeps the eager loop** — verified that its keyed-edge attr access
(`G[u][v][k]`) does NOT store the lazily-materialised dict, so dropping it would
break `G[u][v][k] is G[u][v][k]` identity. Only the simple-DiGraph converter is
made lazy.

Touched: `crates/fnx-python/src/generators.rs` (`report_to_pydigraph`).

## Proof (nx-exact)
`harness_proof.py`: 22 cases — fast_gnp/gnp directed ×5 seeds, gn/gnr/gnc ×3,
scale_free (MultiDiGraph) ×3. **0 mismatches vs nx** on ordered fingerprint
(nodes+attrs, edges(keys,data) in adj order, graph dict). Edge-attr identity +
post-hoc mutation verified per case (simple DiGraph lazy + MultiDiGraph eager).
Golden sha256 (== nx):
`05463c627c8fa658624c0fe0c226bcae849101c96dfd697bd3d940ed5a0b9642`
pytest -k "gnp/generator/...": **2269 passed**.

## Timing (warm interleaved min-of-5, backend disabled, fast_gnp_random_graph directed, p=0.05)
| n    | baseline fnx | nx       | baseline ratio | new fnx  | new ratio | self-speedup |
|------|-------------:|---------:|---------------:|---------:|----------:|-------------:|
| 1000 |    83.3 ms   | 38.3 ms  |     2.19×      |  74.2 ms |   1.94×   |    1.12×     |
| 1500 |   246.1 ms   | 90.7 ms  |     2.76×      | 217.0 ms |   2.39×   |    1.13×     |
| 2000 |   473.0 ms   | 160.9 ms |     2.92×      | 382.6 ms |   2.38×   |    1.24×     |

~1.13–1.24× self-speedup, byte-exact, cascading across all simple-directed
generators. HONEST RESIDUAL: the function remains ~2.4× slower than nx — the
dominant cost is the inner dense-DiGraph construction (succ/pred index + edges
IndexMap for O(E) edges), the deferred bulk-construction substrate, NOT the
edge-attr dicts. This lever removes the edge-attr slice only.

## Score
Impact: moderate (1.13–1.24× self-speedup across 5 directed generators,
construction-tax slice). Confidence: very high (byte-identical golden sha +
identity + mutation, 0/22, 2269 tests). Effort: very low (delete one loop). Score
>= 2.0 by low-effort/high-confidence; explicitly NOT the full directed-generator
gap (inner construction substrate remains).
