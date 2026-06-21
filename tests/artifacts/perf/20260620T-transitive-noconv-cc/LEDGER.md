# Perf WIN (code-only) — transitive_closure / transitive_reduction skip redundant _from_nx_graph (br-r37-c1-tcnoconv)

- Agent: `BlackThrush` · 2026-06-20 · File: `python/franken_networkx/dag.py`
- DISK-CRITICAL turn: code-only, NO cargo/compile. Parity + conformance via existing install.

Same lever as contracted_* (br-r37-c1-contractnoconv): `transitive_closure` and
`transitive_reduction` are NOT registered fnx backends, so `nx.transitive_*(fnx_G)`
runs nx's raw algorithm over the fnx graph, which starts from `TC = G.copy()` — so
the result is ALREADY an fnx graph, byte-identical to nx-on-an-nx-graph. The
unconditional `_from_nx_graph` was a pure redundant O(V+E) re-conversion. Return
the already-fnx result directly (gated on isinstance fnx graph; nx-typed inputs
still convert). Discriminated via a shared `_fnx_result_or_convert` helper.

NOTE: k_core/k_shell/k_crust/k_corona, transitive_closure_dag, dag_to_branching,
eulerize, metric_closure all return NX graphs (dispatched / new-graph builders) —
the conversion IS needed there; the isinstance gate leaves them untouched.

## Parity (existing install, no build)
- fnx.dag.transitive_closure vs nx-on-nx: 1500/1500 (DiGraph + undirected, reflexive
  False/True/None, node+edge attrs, returns fnx type).
- fnx.dag.transitive_reduction vs nx-on-nx: 1000/1000 (DAGs, attrs, returns fnx).
- pytest -k 'transitive or dag': 755 passed.

## Perf
BENCH DEFERRED (disk-critical). Win = skip the whole _from_nx_graph conversion per
call. Measure when disk recovers.
