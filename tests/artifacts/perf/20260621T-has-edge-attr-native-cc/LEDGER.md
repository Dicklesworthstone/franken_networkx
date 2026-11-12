# Perf WIN — _graph_has_edge_attribute / _mst_has_weight_edge_attr native gate: voronoi 0.66x->1.06x, multi_source_dijkstra_path 0.43x->0.67x (br-r37-c1-hasattrnative)

- Agent: `BlackThrush` · 2026-06-21 · File: `__init__.py`

## The gap (profiled)
Profiling multi_source_dijkstra_path (unweighted, 0.43x) showed a single 420us line: the
weighted-dijkstra/MST delegation GATE `_mst_has_weight_edge_attr` (and `_graph_has_edge_
attribute`) walked `G.edges(data=True)` — materializing the full EdgeDataView (attr dict per
edge) just to answer "does any edge carry the weight attr". 420us of a 1287us call; run on
EVERY dijkstra call (4 gate callers). (The kernel itself is 737us / TealSpring's fnx-algorithms
file; the weighted family delegates due to a kernel weight-ignoring bug and is NOT a my-file
fix — in-process nx-on-fnx is per-access-bound, 3530us vs 3925us. Recorded as negative evidence.)

## The fix
Route both helpers through the existing native `graph_has_edge_attr` binding (scans the Rust-
side edge_py_attrs, ~0.1us — 3000x), with the Python `G.edges(data=True)` fallback for
multigraphs (native returns None) and non-str names.

## Verify
- Native == G.edges(data=True) ref BYTE-IDENTICAL 3500/3500 (simple Graph/DiGraph, every
  weight path: constructor/add_edge(weight=)/add_weighted_edges_from/assign/copy/subgraph/
  convert/relabel). Gate DECISION new==old 800/800 -> correctness-neutral (delegation path
  unchanged). pytest -k 'dijkstra/voronoi/spanning_tree/mst' 1234 passed.

## MEASURED (nx/fnx, warm min)
| fn | before | after |
|----|--------|-------|
| voronoi_cells (unweighted) | 0.66x | 1.06x |
| multi_source_dijkstra_path (unweighted) | 0.43x | 0.67x |
| single_source_dijkstra | (win) | 4.44x |

voronoi flips to a win; the 420us gate is gone for all 4 callers. (multi_source_dijkstra_path's
residual 0.67x is the native kernel being slower than nx's Python + the order reorder — both
TealSpring's fnx-algorithms kernel.)
