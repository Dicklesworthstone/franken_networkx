# br-r37-c1-57dlh Isomorphism Proof

## Change

Replace the `find_cycle` NetworkX parity fallback with an in-process mirror of
NetworkX `edge_dfs` plus `find_cycle` backtracking over fnx graph views.

## Behavior Invariants

- Ordering preserved: yes. `_fnx_edge_dfs` mirrors NetworkX `edge_dfs` and uses
  `G.nbunch_iter`, `G.edges`, and `G.in_edges` in the same source and
  orientation order.
- Tie-breaking unchanged: yes. The first DFS-discovered cycle still wins; the
  backtracking loop is the NetworkX loop, including `previous_head`,
  `active_nodes`, and final prefix trimming.
- Floating-point: N/A.
- RNG seeds: N/A.
- Exceptions preserved: yes. The golden corpus includes no-cycle, missing
  source, and invalid orientation cases.
- Multigraph keys preserved: yes. The golden corpus includes `MultiGraph` and
  `MultiDiGraph` key order cases.

## Golden Output

Baseline and after golden output are byte-identical:

```text
70bce758312b79f97733a3b03a9e27dac6d753eae7b987ec467a6962f28d1771  baseline_golden.jsonl
70bce758312b79f97733a3b03a9e27dac6d753eae7b987ec467a6962f28d1771  after_golden.jsonl
golden_diff.txt: 0 bytes
```

Golden cases: directed divergence repro, directed backtracking, scalar source,
source list order, missing source, orientation original/reverse/ignore, DAG
no-cycle, self-loop, invalid orientation, undirected edge direction,
undirected orientation, undirected no-cycle, keyed multigraphs.

## Verification

```text
python3 -m pytest -q -p no:cacheprovider \
  tests/python/test_find_cycle_directed_parity.py \
  tests/python/test_find_cycle_undirected_direction_parity.py \
  tests/python/test_cycle_conformance.py \
  tests/python/test_traversal_additional.py::test_edge_dfs_none_source_matches_networkx_without_fallback \
  tests/python/test_traversal_additional.py::test_edge_dfs_orientation_ignore_matches_networkx_without_fallback

154 passed in 0.70s
```

```text
python3 -m py_compile \
  python/franken_networkx/__init__.py \
  tests/python/test_find_cycle_directed_parity.py \
  tests/artifacts/perf/20260608T-find-cycle-early-exit-tealspring/bench_find_cycle.py \
  tests/artifacts/perf/20260608T-find-cycle-early-exit-tealspring/golden_find_cycle.py

pass
```
