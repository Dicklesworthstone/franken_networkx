# Alien Recommendation Card: Directed Native Adjacency Materialization

- Bead: `br-r37-c1-nocb2`
- Symptom: `DiGraph.to_dict_of_dicts` and `DiGraph.to_dict_of_lists` were slower than upstream NetworkX because exact `DiGraph` fell through to Python `AdjacencyView` / `neighbors()` wrappers.
- Profile match:
  - `to_dict_of_dicts`: Python wrapper/adaptor path consumed `1.166s` over 20 conversions.
  - `to_dict_of_lists`: Python wrapper/adaptor path consumed `0.324s` over 20 conversions.
- Graveyard primitive:
  - Cache-aware/vectorized execution principle from the FrankenSuite graveyard: move repeated dynamic wrapper traversal into a tight native ordered materialization pass over the already-owned adjacency structure.
  - This is the graph-adjacency version of projection pushdown/deforestation: remove intermediate view objects while preserving the same ordered relation.
- Chosen lever:
  - Extend the existing native simple-graph `to_dict_of_*` builders from exact undirected `Graph` to exact `DiGraph`.
  - Use `nodes_ordered()` and `successors_iter(u)` for the output traversal order.
  - Use directed `(u, v)` keys for live edge-attribute dict reuse.
- Fallback:
  - Non-exact graph types, subclasses, filtered views, multigraphs, `nodelist`, and `edge_data` overrides still take the existing Python general path.
- EV:
  - Impact 5, confidence 4, effort 2, score 10.0.
