# BOLD-VERIFY bead triage — MEASURED ratios for ready perf beads (BlackThrush, 2026-06-21)

Swept `br ready` perf beads + broad algorithm/generator head-to-head. fnx DOMINATES the
algorithm surface; the open beads are substrate / parity-blocked / constant-factor.
Recorded so the next session targets the one tractable high-value lever directly.

## MEASURED (nx/fnx, >1 = fnx WINS), warm min-of-N, taskset+PYTHONHASHSEED=0
| function (bead)                       | ratio | abs gap | verdict |
|---------------------------------------|-------|---------|---------|
| copy.deepcopy(Graph)      (489mp)     | 0.58x | ~5 ms   | LOSS — TRACTABLE LEVER (below) |
| copy.deepcopy(MultiGraph) (489mp)     | 0.37x | ~14 ms  | LOSS — same lever |
| copy.deepcopy(DiGraph)                | 0.99x | —       | neutral |
| max_weight_clique (gqvoh)             | 0.42x | ~2.3 ms | PARITY-BLOCKED — see below |
| nodes_with_selfloops (up5ig)          | 0.52x | ~0.05ms | LOSS but micro-abs (PyO3 scan vs nx C) |
| selfloop_edges / number_of_selfloops  | 0.49-0.73x | micro | same — constant-factor PyO3 floor |
| effective_size DIRECTED (qbj9u)       | 0.51x | ~2.3 ms | LOSS — needs a native DIRECTED kernel |
| MultiGraph.copy() (jelx1)             | 0.80x | substrate | String-keyed substrate (yl606) |
| effective_size UNDIRECTED             | 4.81x | —       | WIN (sanity) |

## PARITY-BLOCKED: max_weight_clique (gqvoh) — do NOT de-delegate
A native `_fnx.max_weight_clique` kernel EXISTS and the returned WEIGHT is byte-exact vs
nx (0/800 mismatch). But the returned CLIQUE diverges in 113/800 (14%): when multiple
max-weight cliques tie, the kernel's branch-and-bound picks a different one than nx, and
even on matching sets the order differs ([0,1,2] vs nx [1,0,2]). Like the clique-family /
set-order functions, the clique result is tie/search-order sensitive -> cannot be matched
in safe Rust. STAYS delegated. (Confirms why br-r37-c1-07gkp abandoned the native path.)

## TRACTABLE LEVER (scoped for clean execution): native same-type deepcopy (489mp)
ROOT CAUSE (cProfile, Graph(1000,4000)): `_graph_deepcopy` (Python override, __init__.py
~6108) shallow-copies the structure then deep-copies attrs via a per-node/edge AtlasView
loop — `out[u][v]` hits `_cached_adj_row_keydict` / `_native_adjacency_row_dict` 17680x
(per-access row-keydict rebuild). That walk is the whole gap. A Python in-place fix is
BLOCKED: fnx `edges(data=True)` materializes COPIES, not live dicts, so mutation won't
persist.
THE FIX (Rust, next session): add `_native_deepcopy(&self, py, memo)` per type, modeled on
`_native_copy` (lib.rs:6096 / digraph.rs:3829 etc.) but swapping the shallow
`py_dict_to_attr_map_with_mirror` (.copy()) for `deepcopy_py_dict` (lib.rs:631, already
used by `_native_to_undirected_deepcopy`). Then route `_graph_deepcopy` to
`self._native_deepcopy(memo)` and keep ONLY the thin Python tail (frozen flag + custom
instance attrs). Correctness gates: deep nested-mutable independence, shared-memo cross-
attr identity, frozen preservation, custom `g.attr=` preservation. Expected: Graph 0.58x
-> ~parity-or-win, MultiGraph 0.37x -> big gain. NOT rushed here — correctness-critical
(deepcopy mutation isolation) deserves a full build+verify pass, not a low-budget patch.

## This turn's net: 0 ship (no regression introduced), 1 lever fully scoped w/ profile +
## root-cause, 1 bead proven parity-blocked (negative evidence). REVERT discipline intact.
