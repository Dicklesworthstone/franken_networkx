# Perf WIN — native deepcopy extended to directed: MultiDiGraph 0.54x->1.63x (br-r37-c1-489mp follow-up)

- Agent: `BlackThrush` · 2026-06-21 · File: `crates/fnx-python/src/digraph.rs`
- Follow-up to the PyGraph/PyMultiGraph native deepcopy (876eb3ec3). Same pattern.

## Change
Added `_native_deepcopy(&self, py, memo)` to PyDiGraph + PyMultiDiGraph: VERBATIM
structure via `__copy__` (preserves source succ/pred row order + the succ/pred/edge
row-key override maps) + deep-copied node/edge attr dicts under one shared memo
(`crate::deepcopy_py_dict_memo`). The Python `_graph_deepcopy` override already routes
via `hasattr` — no __init__.py change needed. All 4 graph types now take the native path.

## Verify
- BYTE-EXACT vs nx deepcopy 800/800 (DiGraph + MultiDiGraph x400: nodes + edges(data) +
  succ adj order + PRED adj order + graph/node attrs). Deep mutation isolation holds.
- pytest -k 'deepcopy/copy/pickle/frozen/freeze/reverse' 1535 passed.

## MEASURED (nx/fnx, warm min-8)
| case                          | before | after  |
|-------------------------------|--------|--------|
| deepcopy(MultiDiGraph) attr   | 0.54x  | 1.63x  (19.7 -> ~10ms) |
| deepcopy(DiGraph) attr        | 0.97x  | 0.96x  (neutral) |
| deepcopy(DiGraph) bare        | —      | 0.99x  (neutral) |

MultiDiGraph flipped to a win. DiGraph stays ~parity: profiling shows it is NOT
attr-bound (the native attr deep-copy is cheap) but `__copy__`-bound — cloning the
succ_py_keys + pred_py_keys + edge_py_keys row-key override maps dominates. The native
path removed the per-edge AtlasView walk (no regression, byte-exact) but cannot beat nx
until those row-key clones are cheaper. FOLLOW-UP: native bulk clone_row_keys (a separate
lever) would lift DiGraph deepcopy to a win too.
