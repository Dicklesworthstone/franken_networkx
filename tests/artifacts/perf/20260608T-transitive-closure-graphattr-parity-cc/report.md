# transitive_closure: preserve graph-level attributes (br-r37-c1-mstminattr sibling)

## Bug (behavior parity)
The native transitive_closure path (cyclic DiGraph, br-r37-c1-tc-cyclic) copied
NODE and EDGE attrs from G onto the result but NOT graph-level attrs. nx's
`TC = G.copy()` carries `G.graph`, so `transitive_closure(G).graph` diverged
(`{}` vs nx's populated dict). Found by a systematic graph/node-attr-drop audit
of graph-returning functions (the same class as the minimum_spanning_tree fix).

## Fix
Add `result.graph.update(dict(G.graph))` alongside the existing node/edge copy.

## Proof
- 70 directed graphs (graph/node/edge attrs x cycles): 0 mismatches on type,
  node-data, edge-set, graph attrs vs nx; golden fnx==nx.
- `pytest -k transitive`: 41 passed.
