# EdgeView __iter__ lazy attr lookup (br-r37-c1-7gxek)

EdgeView::__iter__ (crates/fnx-python/src/views.rs) computed
`PyGraph::edge_key(left, right)` (2 String clones) + `edge_py_attrs.get(&ek)`
(hashmap probe hashing 2 strings) for EVERY edge, before the data-variant match.
For the common `G.edges()` (NoData) path those results are discarded. Moved the
edge_key + lookup INSIDE the AllData/Attr/AttrWithDefault branches that use them.

Isomorphism: pure laziness -- the emitted tuples are byte-identical for every
variant (NoData / data=True / data='attr' / data='attr',default). Golden over
all four variants across 3 BA graphs (weighted) is 0-mismatch vs networkx and
unchanged:

    EDGES_GOLDEN a615bca05fc5f2fe2ba3a817400c91139002b378d93aa0bfe76d47ca4fcf2403

1074 edge/view pytest cases + clippy -D warnings pass.

Bench (edges() on BA(1500,4), min-of-80, load-robust; medians were noise-bound):
    before: 2.03 ms
    after : 1.62 ms   -> 1.25x

Opportunity Score = Impact 2 x Confidence 5 / Effort 1 = 10.
