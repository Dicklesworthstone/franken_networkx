# perf: _fnx_to_nx directed MultiDiGraph conversion — native predecessor-keys bulk reader

Bead: br-r37-c1-i5cf1 (directed half; undirected shipped 3eec03000). The MultiDiGraph
branch of _fnx_to_nx walked AtlasViews per edge AND _align_rows re-walked fg.adj/fg.pred
per node — a 500-node MultiDiGraph conversion took ~12.3 SECONDS. The blocker for a fast
path was the _pred row order: nx _pred must follow fg's pred (edge-insertion) order, which
had no cheap Python source (succ-major edges give the wrong order; {v:list(fg.pred[v])} is
the O(V*deg) AtlasView walk).

## Lever (ONE)
Add a native Rust bulk reader ``PyMultiDiGraph::_native_predecessor_keys_bulk`` returning
``[(node, [pred,...]), ...]`` in nodes_ordered order, each pred list in inner.predecessors
(== fg.pred / edge-insertion) order with the z6uka display-key override. backend.py's
directed-multigraph path now builds from the fast native bulk edge view and realigns
``_succ`` from ``adjacency()`` and ``_pred`` from this new bulk — no per-node AtlasView walk.

## Proof (byte-exact)
- Directed-MG conversion fingerprint SHA over an 11-graph corpus (self-loops, antiparallel,
  isolated, string nodes, shuffled-insertion-order to stress pred order): NEW == OLD backend,
  310a2021e582a7cb302de3e020431db62dd9e6332345389cdc45bd72ba889cc2. Fingerprint covers
  node order+data, edges(keys,data), SUCC rows, PRED rows, graph attrs.
- test_fnx_to_nx_row_parity: 10 passed (incl MultiDiGraph). succ/pred rows match fg exactly;
  succ/pred datadict sharing invariant holds. 10508 multigraph/convert/conformance tests pass.

## Benchmark
| metric                                          | OLD        | NEW      | speedup |
|-------------------------------------------------|------------|----------|---------|
| _fnx_to_nx(MultiDiGraph) n=500                  | 12351 ms   | 28.9 ms  | 427x    |
| degree_assortativity_coefficient(weight=) n=300 | 2384 ms    | 89 ms    | 26.7x   |
| complement(MultiDiGraph) n=300                  | 3039 ms    | 762 ms   | 4.0x    |

Byte-identical to the old path; every delegated directed-multigraph function inherits it.
