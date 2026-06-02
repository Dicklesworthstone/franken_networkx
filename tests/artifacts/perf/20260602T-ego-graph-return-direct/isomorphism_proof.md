# Isomorphism Proof: ego_graph Direct fnx Return

## Change

`python/franken_networkx/__init__.py::ego_graph` now returns the concrete fnx graph it already constructs instead of passing that graph through `_from_nx_graph`.

## Behavioral Invariants

- Ordering preserved: `ordered_nodes` is still computed from `G.nodes()` filtered by `nodes_within`, and edges are still copied by iterating `G.edges(...)` in the same order.
- Tie-breaking unchanged: BFS discovery and weighted-distance selection are unchanged; only the final representation copy is removed.
- Node and edge data preserved: the same `graph.add_node(..., **dict(G.nodes[node]))` and `graph.add_edge(..., **data)` calls populate the returned graph.
- `center=False` preserved: the center node is still removed before return.
- Directed and undirected handling preserved: the `undirected` branch, directed successor/predecessor traversal, and multigraph edge-copy branches are unchanged.
- Floating point: weighted distance comparisons are unchanged; no new arithmetic is introduced.
- RNG: none.
- Error classes: missing source, NaN radius handling, and NetworkX fallback gates are unchanged.

## Golden Verification

- Baseline fnx sample sha256: `4db403d99bf3742c4261ba39968be657e7dbf94788fabbf69fc9f3e9532e0eed`.
- Baseline NetworkX sample sha256: `4db403d99bf3742c4261ba39968be657e7dbf94788fabbf69fc9f3e9532e0eed`.
- After fnx sample sha256: `4db403d99bf3742c4261ba39968be657e7dbf94788fabbf69fc9f3e9532e0eed`.

Focused parity tests:

```text
.venv/bin/python -m pytest \
  tests/python/test_ego_graph_node_order_parity.py \
  tests/python/test_quickwin_rewire_parity.py::test_ego_graph_matches_nx \
  tests/python/test_native_replacements_parity.py::TestEgoGraph \
  tests/python/test_coverage_gaps.py::TestGenerators::test_ego_graph_and_from_dict_of_dicts_match_networkx_contract \
  tests/python/test_review_mode_regression_lock.py::test_ego_graph_missing_source_and_nan_radius_match_nx -q

15 passed in 0.45s
```
