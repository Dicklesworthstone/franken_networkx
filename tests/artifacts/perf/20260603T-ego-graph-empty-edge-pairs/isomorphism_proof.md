# br-r37-c1-04z53.29 Isomorphism Proof

## Code Lever

Only the empty-data branch in `ego_graph` simple-Graph edge copying changed:

- Before: empty edge data appended `(u, v, data)` where `data == {}`
- After: empty edge data appends `(u, v)`

All non-empty data paths are unchanged. The non-string attribute-key path still calls `graph.add_edge(u, v, **data)` exactly as before.

## Observable Semantics

- Node discovery is unchanged. The radius, weighted-radius, directed, undirected, and `center` logic is not edited.
- Node output order is unchanged. The result still filters `G.nodes()` in original graph order.
- Edge filtering is unchanged. The loop still walks the same `edge_source` and applies the same `u in nodes_within and v in nodes_within` predicate.
- Edge order is unchanged. Empty-data edges are appended to `edges_to_add` at the same point in the same loop.
- Edge orientation is unchanged. The tuple still uses the original `(u, v)` yielded by `G.edges(data=True)`.
- Existing result graph state is empty except for copied nodes before edge insertion, so NetworkX-observable `add_edges_from([(u, v, {})])` and `add_edges_from([(u, v)])` both create the same edge with an empty attribute dict.
- Non-empty edge attributes are unchanged and still pass through `(u, v, data)` or the non-string-key fallback.
- MultiGraph and MultiDiGraph behavior is unchanged because the edit is only in the non-multigraph branch.

## Determinism

- Tie-breaking: unchanged. The BFS queue, node order filter, and edge-source order are identical.
- Floating point: unchanged. The edited path does not perform arithmetic.
- RNG: unchanged. Bench and golden generation use the same fixed seed (`42`); the edited path does not sample random values.
- Attribute aliasing: unchanged for empty dict edges because there is no payload to alias. Non-empty data stays on the same triple path as before.

## Golden Evidence

- Baseline fnx digest: `a66fe1d2d36fe1f69a5966fab6d739d8b5b34ed0aae622b17565fbba8ce603d6`
- After fnx digest: `a66fe1d2d36fe1f69a5966fab6d739d8b5b34ed0aae622b17565fbba8ce603d6`
- NetworkX oracle digest: `a66fe1d2d36fe1f69a5966fab6d739d8b5b34ed0aae622b17565fbba8ce603d6`
- `sha256sum -c tests/artifacts/perf/20260603T-ego-graph-empty-edge-pairs/baseline_sha256.txt`: passed from repo root.
- `sha256sum -c tests/artifacts/perf/20260603T-ego-graph-empty-edge-pairs/after_sha256.txt`: passed from repo root.

## Focused Parity

`rch exec -- env PYTHONPATH=python .venv/bin/python -m pytest tests/python/test_ego_graph_node_order_parity.py tests/python/test_native_replacements_parity.py::TestEgoGraph tests/python/test_quickwin_rewire_parity.py::test_ego_graph_matches_nx -q`

Result: `13 passed in 0.41s`.

These tests cover node order, edge set parity, center removal, radius zero, directed graph traversal, undirected traversal over directed input, weighted-distance radius, and native replacement behavior against NetworkX.
