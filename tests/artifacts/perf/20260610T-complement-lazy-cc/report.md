# perf(complement): lazy edge-attr dicts

br-r37-c1-cqfgt

## Problem
The native `complement` kernel (PyGraph + PyDiGraph branches) inserted edges into
the inner integer adjacency via `extend_edges_unrecorded` (fast), then ran a
SECOND pass allocating an empty `PyDict::new(py)` into `edge_py_attrs` **for every
complement edge** (plus a `PyGraph::edge_key` String-tuple per edge). The
complement of a sparse graph is DENSE (~V²/2 edges), so this was O(V²) wasted
PyDict allocations + String tuples — the construction tax that left `complement`
**1.06–1.24× slower than nx** despite the fast inner insertion (n=2000:
2.80 s vs nx 2.26 s).

## Lever (one)
Drop the eager per-edge `edge_py_attrs` population. `materialize_edge_py_attrs`
(used by every `G[u][v]` / `edges(data=True)` / `to_dict_of_dicts` path) already
`or_insert_with(PyDict::new)` lazily on first access and stores the result, so
repeat access returns the SAME object (`G[u][v] is G[u][v]` identity holds). The
complement carries no edge data, so lazy materialisation is byte-identical to the
eager allocation — it just defers (and usually avoids) the allocation.

Touched: `crates/fnx-python/src/algorithms.rs` (`complement`, both branches).

## Proof (nx-exact)
`harness_proof.py`: 13 cases — gnp undirected ×6 + directed ×3, self-loops +
node/graph attrs, string labels, empty, single edge. **0 mismatches vs nx** on an
ordered fingerprint (nodes+attrs, edges(data) in adj order, graph dict). Edge-attr
**identity** (`C[u][v] is C[u][v]`) and **post-hoc mutation** (`C[u][v]["w"]=1`)
verified per case. Golden sha256 (== nx):
`62ccc0fde8ee9c331d198096b854a00ba9178cd98ba95f482b71307a88445385`
pytest -k complement: **186 passed, 1 skipped**.

## Timing (warm interleaved min-of-5, backend disabled, gnp(n,0.02) complement)
| n    | baseline fnx | nx        | baseline ratio | new fnx   | new ratio | self-speedup |
|------|-------------:|----------:|---------------:|----------:|----------:|-------------:|
| 1000 |   579.0 ms   |  501.8 ms |     1.06×      |  210.4 ms | **0.42×** |    2.75×     |
| 1500 |  1413.6 ms   | 1189.6 ms |     1.17×      |  597.2 ms | **0.50×** |    2.37×     |
| 2000 |  2802.8 ms   | 2171.0 ms |     1.24×      | 1106.1 ms | **0.51×** |    2.53×     |

1.06–1.24× slower → ~0.5× (2× faster than nx), 2.4–2.75× self-speedup (1.7 s saved
at n=2000).

## Score
Impact: high (construction-tax lever, 2× faster than nx, ~1.7 s absolute on a
dense O(V²) result). Confidence: high (byte-identical golden sha + identity +
mutation, 0/13 incl. directed/self-loop/attrs, 186 tests). Effort: low (delete an
eager alloc loop; lazy path already exists). Score >> 2.0.
