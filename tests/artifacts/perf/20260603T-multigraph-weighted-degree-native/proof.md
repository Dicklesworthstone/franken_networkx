# MultiGraph/MultiDiGraph weighted degree native fast path (br-r37-c1-0lsoq / wdeg)

## Root cause
`MG.degree(weight='w')` / `MDG.degree(weight='w')` produce a
`MultiGraphDegreeView` / `MultiDiGraphDegreeView` (python/franken_networkx).
Their `__iter__` yielded `(node, self[node])`, and `self[node]` called the
module-level `degree(G, node, weight)`, which walks `G.adj[node]` /
`G.succ[node]`+`G.pred[node]` via the MultiAdjacencyView lambda chain plus
`keydict.values()` per neighbor — O(degree) of pure-Python view machinery per
node, so `list(G.degree(weight=w))` was ~13000x (undirected) / ~5400x
(directed) slower than networkx.

## Lever
Added `PyMultiGraph::_native_weighted_degree(weight)` and
`PyMultiDiGraph::_native_weighted_degree(weight)` (non-shadowed native methods)
returning the full `(node, total)` sequence in node order, reading the live
edge attr dicts (`edge_py_attrs`) directly from inner adjacency. The two degree
views' `__iter__` route to it when iterating all nodes with a string weight;
the single-node / nbunch-subset paths fall back unchanged.

## FP / numeric isomorphism (the subtle part)
networkx's `MultiDegreeView` / `DiMultiDegreeView` compute the weighted total
with a **flat `sum()`** generator, NOT a per-neighbor grouped fold:

    # MultiDegreeView (undirected)
    deg = sum(d.get(weight,1) for key_dict in nbrs.values() for d in key_dict.values())
    if n in nbrs:                       # self-loop
        deg += sum(d.get(weight,1) for d in nbrs[n].values())

    # DiMultiDegreeView (directed total)
    deg = sum(<flat over succ>) + sum(<flat over pred>)   # two separate sums

CPython's `sum` is Neumaier-compensated for floats and the association of the
running total matters, so the previous per-neighbor `edge_total` grouping (and
inline `edge_total * 2` self-loop doubling) drifted ~1 ULP from nx. The native
methods build the value list in nx's exact (neighbor-major, key-minor) order and
call the SAME builtin `sum`, so the result is bit-identical including numeric
type (int 0 accumulator, default weight `1`). The pre-existing module-level
`degree()` single-node path had the same association bug — fixed it to use the
identical flat-`sum()` form (covers all 4 graph kinds).

## Golden (MultiGraph + MultiDiGraph; 3 seeds x self-loops on/off; int + float +
## missing weights; multi-edges; bulk + single-node + nbunch paths)

    mismatches=0
    WDEG_GOLDEN 48b72dd4f6c1e24b410cdb2cfaaeb181b6c04c1ca9f78012dfd644198111cd4e

Compared exact value, iteration order, AND Python value type vs networkx.
2575 degree/multigraph + 2036 weight/assortativity/histogram pytest cases and
`clippy -D warnings` pass.

## Benchmark (degree(weight='w') over a 900-edge graph on 300 nodes, median)

    MultiGraph    before: 5064.257 ms   after: 0.390 ms   -> 12985x
    MultiDiGraph  before: 2434.962 ms   after: 0.454 ms   ->  5363x

Opportunity Score = Impact 5 x Confidence 5 / Effort 2 = 12.5.

## Follow-up (not in this lever)
Simple `Graph`/`DiGraph` `degree(weight=)` (`_WeightAwareDegreeView._weighted_value`)
shares the per-neighbor association pattern (~43x/37x gap) — separate bead.
