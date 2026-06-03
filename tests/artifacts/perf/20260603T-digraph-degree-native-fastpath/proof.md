# DiGraph in/out_degree native fast path (br-r37-c1-5670z)

## Root cause
list(D.out_degree())/in_degree() routed through the pure-Python
_DirectedDegreeView._node_degree, whose unweighted simple-graph path did
`len(self._adjacency[node])` -- i.e. len() of the per-node succ/pred AtlasView,
which is O(degree) pure-Python. So list(D.out_degree()) was O(E) in slow Python.
Confirmed degree-proportional: out_degree[deg-0 node]=1.6us vs out_degree[deg-500
node]=98.6us. The undirected G.degree() was already fast (native DegreeView); the
native DiDegreeView existed but was shadowed by the Python property.

## Lever
Added O(1) native methods PyDiGraph::_native_out_degree / _native_in_degree
(crates/fnx-python/src/digraph.rs, registered via the existing #[pymethods]
block -- no lib.rs change) returning inner.out_degree/in_degree
(= successors/predecessors.get(node).len(), O(1)). _node_degree now takes that
fast path for the unweighted, non-multigraph case; weighted and multigraph use
the unchanged general path.

## Isomorphism
Native out_degree(node) = number of distinct successors = len(succ AtlasView[node])
for a simple DiGraph -- identical count. Weighted (slow path) and multigraph are
untouched. Golden over out/in degree lists (order + values), [n] indexing,
callable-with-nbunch, and weighted out_degree across 4 directed gnp graphs is
0-mismatch vs networkx:

    DEG_GOLDEN 3f9d31c915482451948986bd1513c7f641d952cad84f445432250b4f8b933bf0

4402 degree/directed pytest cases + clippy -D warnings pass.

## Benchmark (gnp(2000,0.004,directed), min-of-80, load-robust)
    out_degree(): 11.762ms -> 0.976ms = 12.1x
    in_degree() : 10.434ms -> 1.030ms = 10.1x

Opportunity Score = Impact 5 x Confidence 5 / Effort 2 = 12.5.
