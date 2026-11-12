# Perf WIN — native same-type deepcopy: Graph 0.58x->4.29x, MultiGraph 0.37x->3.96x (br-r37-c1-489mp)

- Agent: `BlackThrush` · 2026-06-21 · Files: `crates/fnx-python/src/lib.rs`, `__init__.py`
- Executes the lever scoped in the prior bead-triage ledger (cProfile root-cause).

## The gap
`copy.deepcopy(G)` routed through the Python `_graph_deepcopy` override, which after a
shallow `copy.copy` deep-copied every node/edge attr dict via a per-element AtlasView
walk: `out[u][v]` rebuilt the native adjacency-row keydict O(E) times (cProfile: 17680
`_cached_adj_row_keydict` calls on a 4k-edge graph — the whole cost). A Python in-place
fix was blocked: fnx `edges(data=True)` yields materialized COPIES, not live dicts.

## The fix
New native `_native_deepcopy(&self, py, memo)` on PyGraph + PyMultiGraph:
clone structure VERBATIM via `__copy__` (NOT `copy()`'s copy-walk reorder — deepcopy must
preserve source adjacency order, matching `copy.copy`), then deep-copy each node/edge
`Py<PyDict>` mirror in Rust under ONE shared `memo`. New helper `deepcopy_py_dict_memo`
mirrors the override's `_dc_attrs` EXACTLY: empty->fresh dict; all values EXACT-type
None/bool/int/float/str -> shallow `dict.copy()`; else `copy.deepcopy(d, memo)` (memo
forwarded so a mutable shared across two attr dicts is copied once). `_graph_deepcopy`
routes to it when present (hasattr guard); graph attrs + frozen flag + custom instance
attrs stay in the shared Python tail. DiGraph/MultiDiGraph (already ~parity 0.99x) keep
the old loop via the guard — unchanged.

## Verify (correctness-critical — deepcopy mutation isolation)
- BYTE-EXACT vs nx deepcopy 1600/1600 (Graph/MultiGraph/DiGraph/MultiDiGraph x400:
  node order + edges(data) + adj row order + graph attrs + node attrs).
- Deep mutation ISOLATION: mutating copy's node/edge/graph nested list|set does NOT
  touch source. MEMO cross-attr identity preserved (shared object stays shared in copy,
  independent of source). FROZEN flag + CUSTOM instance attr preserved.
- pytest -k 'deepcopy or copy or pickle or frozen or freeze' 1086 passed. clippy clean.

## MEASURED (nx/fnx, >1 = fnx WINS), warm min-of-8
| case                              | before | after  |
|-----------------------------------|--------|--------|
| copy.deepcopy(Graph) attributed   | 0.58x  | 4.29x  (11.7 -> 1.79ms) |
| copy.deepcopy(Graph) bare         | —      | 71.06x (0.07ms) |
| copy.deepcopy(MultiGraph) attr    | 0.37x  | 3.96x  (22.0 -> 2.66ms) |

Two big losses flipped to wins. FOLLOW-UP: extend `_native_deepcopy` to PyDiGraph/
PyMultiDiGraph (currently ~parity on the old loop) for symmetry.
