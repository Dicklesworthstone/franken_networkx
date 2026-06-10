# perf(mycielskian): batch construction

br-r37-c1-7o0io

## Problem
`_mycielskian_step` built the result with a **per-edge `R.add_edge`** loop — one
PyO3 crossing + per-edge key/dict construction per edge. The Mycielskian roughly
triples the edge count (old + two shadow passes + apex edges), so this
construction tax was 2.95–3.33× slower than nx (n=400 p=0.06: 34 ms vs 10 ms;
profiling showed the step, not the `convert_node_labels_to_integers` relabel,
was ~all of it).

## Lever (one)
Assemble the result with **batch** `add_nodes_from` / `add_edges_from` (the
at-parity fast path) instead of the per-edge loop: original nodes (with attrs)
+ old edges (with attrs) + shadow node range + the `(u, v+n)` / `(u+n, v)` shadow
edge passes + apex node + apex-to-shadow edges. Node and edge order are
preserved, so the result is byte-identical — only the build path changes.
Python-only.

Touched: `python/franken_networkx/__init__.py` (`_mycielskian_step`).

## Proof (nx-exact)
`harness_proof.py`: 24 cases — gnp ×6, cycle, complete, path, string-labelled
(exercises the integer relabel), node+edge attrs, empty graph × iterations {1, 2}.
Nodes+attrs and edges+attrs **== nx, 0 mismatches**. Edge-attr identity
(`R[u][v] is R[u][v]`) + post-hoc mutation verified.
Golden sha256 (== nx):
`386484126737cb0dcbf86ffb06ff1bbb1f0d1c2269cc81d256b112d36695d03c`
pytest -k mycielsk: **8 passed**.

## Timing (warm interleaved min-of-6, backend disabled, gnp)
| input | baseline fnx | nx | base ratio | new fnx | new ratio | self-speedup |
|-------|-------------:|---:|-----------:|--------:|----------:|-------------:|
| n=200 p=0.1 | 11.61 ms | 3.69 ms | 2.95× | 5.34 ms | 1.45× | 2.17× |
| n=400 p=0.06 | 34.35 ms | 9.49 ms | 3.33× | 13.20 ms | 1.39× | 2.6× |
| n=150 p=0.2 | 11.87 ms | 3.89 ms | 3.01× | 5.75 ms | 1.48× | 2.06× |

2.95–3.33× slower → 1.39–1.48× (2.06–2.6× self-speedup). Residual is the
inherent construction of the ~3× edge set.

## Score
Impact: high (2.06–2.6× self-speedup on a graph-construction primitive).
Confidence: high (byte-identical golden sha + identity + mutation, 0/24 incl.
attrs/string/iterations, 8 tests). Effort: very low (per-edge loop -> batched,
Python-only). Score >> 2.0.
