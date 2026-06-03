# MultiGraph/MultiDiGraph adjacency() native fast path (br-r37-c1-mdadj)

## Root cause
MultiGraph.adjacency / MultiDiGraph.adjacency = _multigraph_adjacency, which
yields `(node, {nbr: dict(keys) for nbr, keys in self.adj[node].items()})` --
unwrapping the per-node MultiAdjacencyView via the lambda chain per element
(~33000x slower than nx). The native PyMultiGraph/PyMultiDiGraph::adjacency()
already builds the full {node: {nbr: {key: attrs}}} snapshot natively (node x nbr
x key order, reusing the live edge attr dicts) but was shadowed by the Python
override.

## Lever
Added non-shadowed PyMultiGraph::_native_adjacency_dict (lib.rs) and
PyMultiDiGraph::_native_adjacency_dict (digraph.rs), each delegating to the
existing native adjacency(). _multigraph_adjacency now returns
iter(self._native_adjacency_dict().items()) when present (hasattr-gated), else
the unchanged Python fallback.

## Isomorphism
Native snapshot = the identical {node: {nbr: {key: attrs}}} dict that
_unwrap(self.adj[node]) builds, same node/nbr/key order, reusing the SAME edge
attr dict objects (verified: adj[u][v][k] is G[u][v][k], mutation-visible).
fnx's adjacency() is a SNAPSHOT by contract (br-r37-c1-adjdict), matched.
Golden over MultiDiGraph + MultiGraph (structure + order + edge data) is
0-mismatch vs networkx:

    ADJ_GOLDEN 0d87ebc7b233afad90dd5575fb58fa453fb0673ea2586869204c7f9ebf682b02

1817 adjacency/multigraph pytest cases + clippy -D warnings pass.

## Benchmark (MultiDiGraph adjacency() on 900-edge graph, median)
    before: 1471.079 ms
    after :    0.362 ms   -> 4063x

Opportunity Score = Impact 5 x Confidence 5 / Effort 2 = 12.5.
