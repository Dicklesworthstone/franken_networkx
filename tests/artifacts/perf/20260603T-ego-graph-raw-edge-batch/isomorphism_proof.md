# ego_graph trusted raw edge batch isomorphism proof

Status: kept candidate.

Observable behavior:
- Node discovery is unchanged. The BFS, directed-undirected, weighted-distance,
  NaN-radius, and `center` logic above result construction is identical.
- Node order is unchanged. `ordered_nodes` is still derived by filtering
  `G.nodes()` in source graph order.
- Edge selection is unchanged. The same `u in nodes_within and v in
  nodes_within` predicate is applied to the same `edge_source`.
- Edge order and orientation are unchanged. `edges_to_add` is populated in the
  same loop order as before and passed as an ordered list to the same raw native
  add routine that the public wrapper delegated to.
- Edge attribute behavior is unchanged. Empty attrs still emit `(u, v)`;
  string-keyed attrs still emit `(u, v, data)`; non-string attr keys still take
  the existing `graph.add_edge(u, v, **data)` fallback.
- Public mutation API behavior is unchanged. The public `Graph.add_edges_from`
  and `DiGraph.add_edges_from` wrappers still validate arbitrary callers. This
  bypass is limited to `ego_graph`'s internally constructed valid batch.
- Error behavior is unchanged for reachable `ego_graph` inputs. Source graph
  nodes cannot be `None` or unhashable because they already exist in `G`; bad
  edge attr-key shapes continue down the pre-existing per-edge fallback.
- Tie-breaking is unchanged. Neighbor traversal, source graph edge iteration,
  and result insertion order are not modified.
- Floating-point behavior is unchanged. The changed block does not perform
  arithmetic; weighted distance calculations remain above it.
- RNG behavior is unchanged. The library path uses no RNG; the benchmark graph
  seed is fixed at `42`.

Golden-output proof:
- Baseline FNX repeat-30 SHA:
  `5dc8ab88ec0fd5490369d69f379aafc838d027576d99d986772bd178131888e3`.
- Baseline NetworkX repeat-30 SHA:
  `5dc8ab88ec0fd5490369d69f379aafc838d027576d99d986772bd178131888e3`.
- Candidate FNX repeat-30 SHA:
  `5dc8ab88ec0fd5490369d69f379aafc838d027576d99d986772bd178131888e3`.
- Baseline and candidate cProfile repeat-20 SHA:
  `4db403d99bf3742c4261ba39968be657e7dbf94788fabbf69fc9f3e9532e0eed`.

Focused parity:
- `tests/python/test_ego_graph_node_order_parity.py`
- `tests/python/test_native_replacements_parity.py::TestEgoGraph::test_ego_graph_undirected_includes_predecessors`
- `tests/python/test_native_replacements_parity.py::TestEgoGraph::test_ego_graph_distance_parameter`
- `tests/python/test_quickwin_rewire_parity.py::test_ego_graph_matches_nx`
- Result: `13 passed`.
