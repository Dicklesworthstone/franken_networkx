# Perf WIN — Multi int-node fast path: MultiGraph 0.28x->0.93x, MultiDiGraph 0.30x->0.78x (br-r37-c1-digbatch)

- Agent: `BlackThrush` · 2026-06-21 · Files: fnx-python/lib.rs, fnx-python/digraph.rs, __init__.py
- Extends the DiGraph int-node fast path (8470addc9) to the multigraph types.

## The gap
The int-node fast path was DiGraph+Graph only. MultiGraph/MultiDiGraph add_nodes_from(range)
fell to the per-node loop: 0.28x / 0.30x nx; int list 0.54x / 0.43x.

## The fix
PyMultiGraph + PyMultiDiGraph `_fast_add_int_nodes` (sibling of PyGraph's; no
lazy_int_node_stop so Py ints are stored), backing the inner insert with the EXISTING
`extend_nodes_with_attrs_unrecorded` + empty AttrMaps (no new inner method). Exact-int
validate-then-mutate; non-int falls through to the attributed batch / per-node loop.
__init__.py add_nodes_from gate widened to (DiGraph, MultiGraph, MultiDiGraph).

## Verify
- BYTE-EXACT vs nx 1500/1500 each (range/list/shuffled order + dedup + mixed-with-edges incl
  parallel edges + keys); attr-node + mixed str/int fallback correct. clippy clean; pytest
  -k 'multigraph/add_nodes/construction/relabel/union/convert/pickle/copy' 4969 passed 0 fail.

## MEASURED (nx/fnx, warm min-12)
| case                                | before | after  |
|-------------------------------------|--------|--------|
| MultiGraph add_nodes_from(range)    | 0.28x  | 0.93x (->0.51ms) |
| MultiDiGraph add_nodes_from(range)  | 0.30x  | 0.78x (->0.77ms) |

3x faster; MultiGraph reaches ~parity, MultiDiGraph improved deep-loss->mild-loss. RESIDUAL:
both capped by the String-keyed succ/pred IndexMap entry per node (the int-CSR substrate,
yl606) — the node insert can't beat nx's C dict until that migrates.
