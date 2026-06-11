# perf: _fnx_to_nx undirected MultiGraph conversion — fast native bulk path

Bead: br-r37-c1-i5cf1. The multigraph branch of backend.py::_fnx_to_nx walked
AtlasViews per edge (_topo_emit_edges_by_adj + fg[u][v]) and then _align_rows
re-walked fg.adj per node — O(V*deg) Python-wrapper round-trips. A 400-node
MultiGraph conversion took ~2584ms, so every delegated undirected-multigraph
algorithm paid hundreds-to-thousands of ms purely in conversion.

## Lever (ONE)
For UNDIRECTED multigraphs: build the nx graph from the fast NATIVE bulk edge view
(`fg.edges(keys=True, data=True)` — node-major adj order, fresh Python-visible
attrs) and realign adjacency rows from the cheap native `fg.adjacency()` snapshot
instead of per-node AtlasView walks. Byte-identical to the old path (edge tuples,
parallel-key order, node/graph attrs, adj row order all preserved).

DIRECTED multigraphs intentionally stay on the old path: their `_pred` rows must
follow fg's pred (edge-insertion) order, which has no cheap Python source — needs a
native predecessor-keys bulk reader (left as the remaining i5cf1 follow-up; the
succ-major emit order would poison bidirectional tie-breaks, guarded by
test_fnx_to_nx_row_parity / br-r37-c1-w7nn3).

## Proof (byte-exact)
- Conversion fingerprint SHA over an 11-graph undirected-multigraph corpus (parallel
  edges, weights, self-loops, isolated, string/mixed nodes): NEW == OLD backend,
  aa6c391fc68c1122dad1086bcb1542f066953b557ff3b30cf5f9ed42e4054f17. Fingerprint
  covers node order+data, edges(keys,data) order, adjacency row order, graph attrs.
- test_fnx_to_nx_row_parity: 10 passed (all 4 classes). 1697 multigraph/convert/
  row-parity tests pass. Remaining full-suite failures (4) are pre-existing ledger
  drift, unaffected by this change.

## Benchmark (undirected MultiGraph, n=400, ~600 base edges + parallels)
| metric                                | OLD       | NEW     | speedup |
|---------------------------------------|-----------|---------|---------|
| _fnx_to_nx(MG) conversion             | 2584 ms   | 8.9 ms  | 290x    |
| degree_assortativity_coefficient(w=)  | 2594 ms   | 51 ms   | 51x     |

Conversion 290x faster, byte-identical; every delegated undirected-multigraph
function inherits it. Pure-Python.
