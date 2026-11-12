# br-r37-c1-z6uka phase 3b — PyMultiDiGraph succ/pred cell display objects

Date: 2026-06-05 · Agent: cc (BlackThrush) · Commit: (this)

## Problem

Phase 3a (321800456) landed PyMultiDiGraph's `succ_py_keys`/`pred_py_keys`
fields as inert scaffolding: declared, initialized empty, cloned in
`__copy__` — never populated, never read. Mixed hash-equal node keys
(28 vs 28.0, True vs 1) through ANY MultiDiGraph edge-add path rendered
adjacency-row neighbors with the node-map object instead of the nx
per-cell object.

`z6uka_break.py` (400 seeded random trials, all four classes, batch +
incremental adds): **115/400 trials diverged, all MultiDiGraph**, on
edges()/adj/pred facets. Graph/DiGraph/MultiGraph clean (phases 1-3a).

## Fix (one lever: wire the existing architecture into PyMultiDiGraph)

Same recipe as PyDiGraph (f48584426) adapted to multigraph cell
semantics (a cell is created by the FIRST key of a (u, v) pair;
parallel keys reuse it; the LAST key's removal drops it):

- populate: `add_edge` gates `maybe_store_row_keys` on `!has_edge(u, v)`
  (new cell). `add_edges_from`/`add_weighted_edges_from`/`update` all
  route through `add_edge`.
- render: successors/predecessors/adjacency/succ/pred getters,
  MultiDiAtlasView (kind-aware: materialize/__iter__/items/copy),
  MultiDiGraphEdgeView v-side.
- maintain: remove_edge (cell-emptying removal only), remove_node(s)
  retain-filter, clear/clear_edges clear.
- derive: copy()/_native_copy keep succ overrides + re-derive pred with
  node objects (nx u-major walk); subgraph/edge_subgraph filter succ to
  surviving cells; reverse() transposes succ overrides into pred-space;
  __copy__ shares both maps.
- __deepcopy__ (Di + MultiDi, Rust level): clone BOTH maps (deepcopy
  preserves dict structure verbatim) — NOTE shadowed by the Python
  wrapper `_graph_deepcopy`, whose rebuild-walk divergence (display
  objects AND pred row order, pre-existing at HEAD, all four classes)
  is filed as br-r37-c1-0ek49.

## Proof

- `z6uka_break.py` / `z6uka_stress.py`: 400/400 random mixed-key trials
  clean (was 115 failures), facets nodes/edges/adj/pred, all classes.
- `z6uka_contract.py`: 12/12 pinned nx contract probes pass (base,
  parallel-reuse, selfloop-asymmetry, one-key-removal keeps cell,
  last-key-removal fresh, remove-node purge, copy, copy-of-copy,
  reverse, reverse-reverse, subgraph-copy, copy.copy). The 13th probe
  (deepcopy) reproduces br-r37-c1-0ek49 at pure HEAD — not a phase-3b
  regression.
- Original bead repro `20260605T-attr-edge-batch-cc/parity_proof.py`:
  90/90, golden corpus sha unchanged
  (275c260de2862d3a7ff011dd1c3d72c59f469573a19bed70df3a57129b1de173).
- 8 new committed tests in test_adj_row_key_parity.py (35 total in file).
- Full pytest sweep: see full_pytest.stdout.
