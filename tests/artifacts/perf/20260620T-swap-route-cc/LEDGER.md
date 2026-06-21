# Perf WIN + consistency fix (code-only) — swap submodule routes fnx graphs to native top-level (br-r37-c1-swaproute)

- Agent: `BlackThrush` · 2026-06-20 · File: `python/franken_networkx/swap.py`
- DISK-LOW turn: code-only, NO cargo. Parity + conformance via existing install.

INVESTIGATION (important — corrects a wrong assumption): fnx's top-level
double_edge_swap INTENTIONALLY diverges from networkx — it uses a fast uniform
edge-pick (O(1) edge selection) instead of nx's degree-CDF node selection, and only
the degree SEQUENCE is contracted (documented: "no exact-output parity is owed").
So a byte-exact-vs-nx rewrite is the WRONG goal (and slower). I verified: top-level
fnx vs nx-on-nx = 36/700 (intentional divergence); a degree-CDF rewrite would
contradict the design + break the submodule/top-level consistency test.

The actual gap: the submodule double_edge_swap / directed_edge_swap DELEGATED every
input to nx's degree-CDF algorithm, which for an fnx graph ran through fnx's slow
per-access adjacency views AND produced output inconsistent with the top-level fnx
function. Fix: dispatch by type — fnx graphs -> the fast native top-level (fnx.
double_edge_swap / directed_edge_swap), genuine nx-typed inputs -> nx's algorithm.

## Parity (existing install, no build)
- submodule(fnx graph) == top-level fnx.double_edge_swap: 1000/1000 (identity + edges).
- submodule(nx graph) == nx.double_edge_swap: 1000/1000 (nx-parity for nx inputs).
- test_nx_edge_swap_dispatchers.py: 13 passed (incl. the previously-failing
  submodule/top-level consistency test); -k 'double_edge_swap or directed_edge_swap'
  all pass.

## Perf
BENCH DEFERRED (disk-low). Win = fnx graphs now use the native uniform-pick (no
degree-CDF + no per-try list(G[u]) adjacency materialization through compat). Measure
when disk recovers.
