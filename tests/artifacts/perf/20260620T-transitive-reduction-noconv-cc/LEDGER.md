# Perf WIN (code-only) — top-level transitive_reduction skip double conversion (br-r37-c1-trnoconv)

- Agent: `BlackThrush` · 2026-06-20 · File: `python/franken_networkx/__init__.py`
- DISK-LOW turn: code-only, NO cargo. Parity + conformance via existing install.

The top-level fnx.transitive_reduction did
``_from_nx_graph(_nx.transitive_reduction(_networkx_graph_for_parity(G)))`` — TWO O(V+E)
conversions (fnx->nx then nx->fnx) around the algorithm. For a concrete fnx DiGraph,
nx.transitive_reduction runs directly over the fnx graph and (deterministic) returns an
fnx DiGraph byte-identical to the converted path. Gate on ``type(G) is DiGraph`` +
isinstance(result, DiGraph) -> return it directly, skipping both conversions. View /
synthetic classes (blaz5 _FilteredGraphView) and non-fnx results fall back to the
conversion path. Mirrors the dag.py submodule transitive_reduction de-delegation
(br-r37-c1-tcnoconv) shipped earlier this session.

## Parity (existing install, no build)
- 3000 random DiGraphs (DAGs + cyclic): byte-exact node/edge order, node/graph attrs,
  DiGraph type; cyclic -> same NetworkXError (0 err mismatches).
- subgraph fallback works; pytest -k transitive_reduction: 76 passed.

## Perf
BENCH DEFERRED (disk-low). Win = skip both O(V+E) conversions for the common DiGraph
case. Measure when disk recovers.
