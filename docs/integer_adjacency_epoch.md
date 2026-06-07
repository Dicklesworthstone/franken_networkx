# Integer-interned adjacency epoch (br-r37-c1-d58s8)

## Why (consolidated evidence)
- pprof: String-keyed adjacency = 68-76% of betweenness/closeness/harmonic
  (reference_perf_profiling_pass).
- cProfile: union/compose residual (~1.5-1.9x vs nx) = 100% inside
  _native_compose with the walk already optimal — per-edge
  EdgeKey(String,String) allocs + String-keyed IndexMap ops.
- Construction-tax deferral br-r37-c1-71x9k (bulk-construction rewrite).
- Every per-source kernel win so far (global_efficiency 12-16x, distance
  measures 16.4x, constraint 2.9x) came from REPLACING String walks with
  integer CSR — this epoch makes that the substrate default.

## Current state (inventory 2026-06-06)
- Graph (fnx-classes/lib.rs): HAS `adj_indices: Vec<Vec<usize>>` parallel
  integer adjacency + `neighbors_indices()` — 27 consumers in
  fnx-algorithms + 4 in fnx-python. EdgeKeyRef gives alloc-free LOOKUP;
  EdgeKey::new (14 insert sites) allocates 2 Strings per stored edge.
- DiGraph: NO integer adjacency at all (successors/predecessors =
  IndexMap<String, IndexSet<String>>); zero index APIs. Directed kernels
  pay full String tax.
- MultiGraph/MultiDiGraph: String-keyed nested maps; keyed bulk APIs
  exist (l5ve7 levers 8-9) but still String-keyed.

## Target architecture
- NodeId = u32; interner = the existing `nodes: IndexMap<String, AttrMap>`
  insertion index (already stable; shift_remove renumbers — see
  invariant I5).
- Adjacency primary: Vec<Vec<NodeId>> in ROW-INSERTION order (the nx row
  semantics); String maps consulted only at boundaries.
- Edge attrs: side-table FxHashMap<(NodeId, NodeId), AttrIdx> (canonical
  min/max for undirected) into a Vec<AttrMap> arena; the String EdgeKey
  IndexMap retained during migration for snapshot/back-compat, then
  boundary-only.
- DiGraph: succ_indices/pred_indices Vec<Vec<NodeId>> mirrors first
  (phase 1), then primary.

## Phases (each = hour-sized levers, one commit each)
P1 DiGraph integer mirrors: succ_indices/pred_indices maintained by
   add/remove paths + successors_indices()/predecessors_indices();
   port the directed BFS family, SPFA, dijkstra kernels (the 68-76%
   holders). Measurable per kernel.
P2 Edge-attr side-table on (NodeId, NodeId): route extends/copy-family
   inserts through it; compose/union stop allocating EdgeKey Strings.
P3 Primary flip: adjacency reads serve from indices; String rows
   derived lazily; remove the dual maintenance.

## Invariants (each broke something once — test before/after EVERY phase)
I1 Row insertion order + u-major-walk semantics (hoist class 1123e2bf8).
I2 Display objects / z6uka row overrides (binding layer untouched).
I3 Mutation partial-error-state semantics (inline add/remove ordering).
I4 apply_row_orders / pickle round-trip / copy walk-reorder parity.
I5 shift_remove renumbering: node removal renumbers IndexMap indices —
   adj_indices already handles this on Graph (study its remove path
   FIRST; DiGraph mirrors must replicate). This is THE hazard.
I6 Ledger/mode semantics (record vs unrecorded paths unchanged).

## Baseline harness
tests/artifacts/perf/20260606T-substrate-epoch-baseline-cc/bench.py —
run on a QUIET host (load < 10) before P1 lands; rerun after each phase.
