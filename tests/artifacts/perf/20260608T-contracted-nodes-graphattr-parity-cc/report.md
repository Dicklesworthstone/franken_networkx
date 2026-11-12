# contracted_nodes / identified_nodes: preserve graph-level attributes (br-r37-c1-mstminattr sibling)

## Bug
nx's contracted_nodes contracts via `H = G.copy()` (preserve_all_attrs=True),
carrying G.graph. fnx's identified_nodes builds a fresh `H = _concrete_class_for(G)()`
and copies node/edge attrs but DROPPED the graph-level attrs (`H.graph == {}` vs
nx's populated dict). Found by the graph/node-attr-drop audit.

## Fix
`H.graph.update(dict(G.graph))` right after constructing H.

## Proof
- 60 contracted_nodes (directed/undirected x self_loops) 0 mismatches on type,
  node-data, edge-set, graph attrs vs nx.
- `pytest -k "contract or identified"`: 420 passed.
