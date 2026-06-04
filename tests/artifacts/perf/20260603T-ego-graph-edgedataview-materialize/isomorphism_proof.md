## br-r37-c1-04z53.25 - ego_graph EdgeDataView materialize bypass

Target: `franken_networkx.ego_graph(Graph, 0, radius=2)` on
BA(3000, 4, seed=42).

Profile-backed baseline:

- Existing bead profile:
  `tests/artifacts/perf/20260603T-ego-graph-r2-current/profile_focused_fnx.txt`
  showed 7 calls in `0.474s`, with `EdgeDataView` fail-fast iteration
  costing `__next__ 0.111s` plus repeated length checks `0.077s`.
- Fresh rch-wrapped sample:
  - fnx mean `0.051675878898822705s`.
  - NetworkX mean `0.022472646298410837s`.
  - normalized graph digest
    `a66fe1d2d36fe1f69a5966fab6d739d8b5b34ed0aae622b17565fbba8ce603d6`.
- Fresh rch-wrapped cProfile:
  - `sample`: `0.491s`.
  - `ego_graph`: `0.451s`.
  - `_FailFastEdgeIterator.__next__`: `0.108s`.
  - repeated `len`: `0.076s`.
  - function calls: `1,037,031`.
- Fresh rch-wrapped hyperfine:
  - `766.3215569685715ms +/- 27.76192726524672ms`.

One lever:

- In the internal non-multigraph edge copy loop, call
  `EdgeDataView._materialize()` directly when `G.edges(data=True)` returns
  this module's `EdgeDataView`.
- For non-`EdgeDataView` edge views and all multigraph paths, behavior is
  unchanged.

After:

- rch-wrapped sample repeat-10 mean:
  `0.04797185050119879s`, 7.17% faster.
- rch-wrapped sample repeat-30 mean:
  `0.04844805789956202s`, 6.12% faster.
- rch-wrapped cProfile:
  - `sample`: `0.446s`.
  - `ego_graph`: `0.381s`.
  - `_FailFastEdgeIterator.__next__`: removed from the hot path.
  - function calls: `449,752`.
- rch-wrapped hyperfine after:
  - repeat-7 command: `738.6953847057144ms +/- 25.79179975392641ms`.
  - repeat-15 command: `687.1420254666667ms +/- 20.92926743006463ms`.
- Score: Impact 2 x Confidence 3 / Effort 1 = 6.0.

Behavior isomorphism:

- Node-set discovery is unchanged. The BFS / weighted-distance logic above the
  copy loop is identical.
- Node insertion order is unchanged. `ordered_nodes` still filters `G.nodes()`
  in original graph order before adding nodes to the result graph.
- Edge order and orientation are unchanged. `EdgeDataView.__iter__` already
  calls `_materialize()` and then wraps the returned list with
  `_FailFastEdgeIterator`; this lever consumes that same materialized list
  directly inside `ego_graph`.
- Edge filtering is unchanged. The same `if u in nodes_within and v in
  nodes_within` predicate is applied before the same `graph.add_edge(u, v,
  **data)` call.
- Edge attribute values are unchanged. `_materialize()` produces the exact
  `(u, v, data)` tuples that the prior iterator yielded.
- Tie-breaking is unchanged. Neighbor traversal, node-set discovery, and graph
  insertion order are not modified.
- Floating-point behavior is unchanged for the unweighted target. Weighted
  `distance` node discovery is outside this lever and the edge-copy loop does
  not perform arithmetic.
- RNG behavior is unchanged. The library path uses no RNG; the benchmark graph
  seed is fixed at `42`.
- Public fail-fast semantics are unchanged. This bypass is only inside
  `ego_graph`'s private copy loop after the source graph and node set are
  fixed; the public `EdgeDataView.__iter__` contract still uses the fail-fast
  iterator.

Golden-output proof:

- Baseline fnx, NetworkX, after repeat-10, after repeat-30, baseline profile,
  and after profile all emitted normalized graph digest
  `a66fe1d2d36fe1f69a5966fab6d739d8b5b34ed0aae622b17565fbba8ce603d6`.
- `sha256sum -c
  tests/artifacts/perf/20260603T-ego-graph-edgedataview-materialize/golden_sha256.txt`:
  passed.

Validation:

- `RCH_ENV_ALLOWLIST=PYTHONPATH rch exec -- env PYTHONPATH=python .venv/bin/python -m py_compile python/franken_networkx/__init__.py`:
  passed.
- `RCH_ENV_ALLOWLIST=PYTHONPATH rch exec -- env PYTHONPATH=python .venv/bin/python -m pytest tests/python/test_ego_graph_node_order_parity.py tests/python/test_native_replacements_parity.py::TestEgoGraph::test_ego_graph_undirected_includes_predecessors tests/python/test_native_replacements_parity.py::TestEgoGraph::test_ego_graph_distance_parameter tests/python/test_quickwin_rewire_parity.py::test_ego_graph_matches_nx -q`:
  13 passed.
- `RCH_ENV_ALLOWLIST=CARGO_TARGET_DIR rch exec -- cargo fmt --package fnx-python --check`:
  passed.
- `RCH_ENV_ALLOWLIST=CARGO_TARGET_DIR rch exec -- cargo check -p fnx-python --all-targets`:
  passed.
- `timeout 180 ubs python/franken_networkx/__init__.py
  tests/artifacts/perf/20260603T-ego-graph-edgedataview-materialize/isomorphism_proof.md`:
  timed out while scanning the large Python wrapper before producing findings.
- `timeout 60 ubs
  tests/artifacts/perf/20260603T-ego-graph-edgedataview-materialize/isomorphism_proof.md`:
  exited 0 with no recognizable language to scan.
