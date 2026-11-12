# MultiDiGraph in/out_degree native fast path (br-r37-c1-kjaqc)

## Root cause
_OutMultiDegreeView / _InMultiDegreeView subclass _DirectedDegreeView, so they
share _node_degree. The br-r37-c1-5670z fast path was guarded `not
is_multigraph()`, so MultiDiGraph fell to the multigraph branch
`sum(len(keydict) for keydict in self._adjacency[node].values())` -- a per-node
walk of the succ/pred AtlasView in pure Python. For a MultiDiGraph this AtlasView
materialization is catastrophic: out_degree() on a 1000-edge graph took 886 ms.

## Lever
Added native PyMultiDiGraph::_native_out_degree / _native_in_degree (existing
#[pymethods] block, no lib.rs change) = inner.out_degree/in_degree
(= successors/predecessors.get(node).values().map(len).sum() -- counts edge
multiplicity, identical to the Python sum). Generalized _node_degree's fast path
to cover BOTH simple and multi directed graphs (dropped the is_multigraph guard;
both PyDiGraph and PyMultiDiGraph now expose the methods). Weighted degree still
uses the unchanged Python path.

## Isomorphism
native out_degree(node) = sum over distinct successors of edge-key-set size =
total out-edges with multiplicity = sum(len(keydict) for keydict in adj.values()).
Golden over out/in degree lists (order+values) + [n] indexing across 3 MultiDiGraph
gnp-style graphs is 0-mismatch vs networkx; weighted out_degree still matches.
3691 multidigraph/degree/directed pytest cases + clippy -D warnings pass.

    MDG_GOLDEN dff345c2aa6bba597892f78bf39998ba70227dc88e50382d9ea9689412992216

## Benchmark (MultiDiGraph out_degree, 1000 edges / 200 nodes, median)
    before: 886.113 ms
    after :   0.068 ms   -> ~13030x  (the slow path made larger graphs hang)

Opportunity Score = Impact 5 x Confidence 5 / Effort 2 = 12.5.
