# Perf WIN (Rust) — pred-row reorder O(E*degree) -> O(E) for DiGraph/MultiDiGraph copy (br-r37-c1-predrebuild)

- Agent: `BlackThrush` · 2026-06-21 · File: `crates/fnx-classes/src/digraph.rs`
- Full build (maturin release, -cc target). warm min-of-6/8 pinned head-to-head vs nx.

## The quadratic
`reorder_pred_rows_for_nx_copy_walk` (called by DiGraph.copy() / MultiDiGraph.copy() /
the copy-walk paths) rebuilt each pred row in nx's u-major order. The integer DiGraph
version did a per-pred-entry LINEAR SEARCH `succ_indices[u].position(|w| w==v)` to find
v's index in u's succ row -> O(E * degree), QUADRATIC on dense directed graphs. The
String MultiDiGraph version did 2 get_index_of lookups per entry + a per-row sort.

## The fix
Rebuild pred rows DIRECTLY by walking succ in (u, succ-index) = pos(u) order and
appending u to pred[v] -> O(E), no search, no sort. Pred rows hold distinct u (DiGraph:
+ parallel multiplicity via succ repeats), so pos(u) is the sole ordering key and the
succ walk reproduces the exact (pos(u), index-of-v-in-succ[u]) order BYTE-IDENTICALLY.

## Verify
- BYTE-EXACT vs nx-on-nx: 2000/2000 (then 800/800) — node order, edge order (+keys for
  multi), AND pred-row + succ-row order, DiGraph + MultiDiGraph, sparse + dense.
- conformance: pytest -k 'copy or reverse or predecessor or digraph or multidigraph'
  3640 passed, 1 skipped. clippy fnx-classes clean.

## MEASURED (nx/fnx, >1 = fnx WINS)
| case                              | after fix |
|-----------------------------------|-----------|
| VERY-DENSE DiGraph.copy (100n/8000e) | 4.53x (0.56ms) |
| SPARSE DiGraph.copy               | 4.53x |
| MultiDiGraph.reverse()            | 3.50x |
| DENSE MultiDiGraph.copy (8000e)   | 0.52x (24.45 -> 20.12ms; still String-substrate-capped, br-r37-c1-yl606) |

The integer-DiGraph quadratic was the lever: removing the O(E*degree) search makes dense
DiGraph.copy() scale linearly (the prior reorder would dominate at high degree). The
MultiDiGraph String version improved ~18% but stays sub-1x (String-keyed storage, needs
int-CSR migration). Both byte-exact, conformance green, no regression -> kept.
