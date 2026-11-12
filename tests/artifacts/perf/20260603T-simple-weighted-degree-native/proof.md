# Graph/DiGraph weighted degree native fast path (br-r37-c1-yo1nt)

## Root cause
`G.degree(weight='w')` on simple Graph/DiGraph goes through
`_WeightAwareDegreeView.__call__`, whose weighted all-node branch returned a
generator `((n, self._weighted_value(n, weight)) for n in G)`. `_weighted_value`
built `dict(G.adj[node])` / `dict(G.succ[node])`+`dict(G.pred[node])` per node —
materializing the AtlasView per node — so `list(G.degree(weight='w'))` was
~34x (undirected) / ~31x (directed) slower than networkx.

## Lever
Added `PyGraph::_native_weighted_degree(weight)` and
`PyDiGraph::_native_weighted_degree(weight)` (native methods) returning the full
`(node, total)` sequence from inner adjacency, reading the live edge attr dicts.
`_WeightAwareDegreeView.__call__` routes its weighted all-node path to the native
method when `_direction is None` (total degree); in/out-degree weighted views and
the single-node / nbunch fallback keep the Python path.

## FP / numeric isomorphism
networkx's `DegreeView` / `DiDegreeView` compute the weighted total as a flat
`sum()` per neighbor group:

    # DegreeView (undirected)
    deg = sum(dd.get(w,1) for dd in nbrs.values())
    if n in nbrs: deg += nbrs[n].get(w,1)        # self-loop counted twice
    # DiDegreeView (directed total)
    deg = sum(<succ>) + sum(<pred>)              # two separate sums added

CPython's `sum` is Neumaier-compensated for floats and the association of the
running total matters, so the previous per-neighbor `total +=` fold drifted ~1
ULP from nx. The native methods build the value list in adjacency order and call
the SAME builtin `sum`, so the result is bit-identical including numeric type.
The single-node / nbunch fallback `_weighted_value` was likewise rewritten from a
continuous fold to the flat per-group `sum()` form.

## Golden (Graph + DiGraph; 3 seeds x self-loops on/off; int+float+missing
## weights; bulk + single-node + nbunch + DiGraph in/out paths)

    mismatches=0
    SWDEG_GOLDEN 23cb1fc3d872b711f05484d6d9c32ec92b15d05db86fa4bf776710b73103017d

Compared exact value, iteration order, AND Python value type vs networkx.
3252 degree/weight/assortativity/bipartite pytest cases and `clippy -D warnings`
pass.

## Benchmark (degree(weight='w') over a 900-edge graph on 300 nodes, median)

    Graph    before: 10.219 ms   after: 0.298 ms   -> 34x
    DiGraph  before:  9.835 ms   after: 0.314 ms   -> 31x

Opportunity Score = Impact 4 x Confidence 5 / Effort 2 = 10.

Completes the weighted-degree no-gap family started in br-r37-c1-0lsoq
(Multi 12985x/5363x). See [[reference_degreeview_flat_sum_ulp]].
