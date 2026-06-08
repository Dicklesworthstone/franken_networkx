# minimum_spanning_tree: preserve graph + node attributes (br-r37-c1-mstminattr)

## Bug (behavior parity)
The native `minimum_spanning_tree` fast path (simple Graph, weighted kruskal)
returned a result that DROPPED graph-level attrs (`result.graph == {}`) and node
attrs (`result.nodes[n] == {}`), while nx preserves both. Edge attrs were already
preserved. Silent divergence — no test caught it. Sibling of the maximum_spanning_tree
fix (br-r37-c1-mstmaxnative) which already restores these; minimum was left behind.

## Fix
Mirror maximum_spanning_tree: after the native call, `result.graph.update(G.graph)`
and copy every node's data. The native binding preserves edge attrs + node
identity; the wrapper restores graph/node attrs so the fast path is byte-identical
to nx (and to the `_from_nx_graph` parity path it replaced).

## Proof (correctness — no timing; host load avg ~22 this window)
- 90 graphs (graph attrs / node attrs / multigraph): 0 mismatches on type, node
  DATA, edge set+weights, and graph attrs vs nx.
- Golden sha256 == nx (`f1001341...`).
- `pytest -k spanning`: 320 passed.
