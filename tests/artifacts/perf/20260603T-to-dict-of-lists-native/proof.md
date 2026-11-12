# to_dict_of_lists native fast path (br-r37-c1-6o3wi)

Mirror of br-r37-c1-yl59j: native `_fnx.to_dict_of_lists_undirected(G)` in the
unreserved crates/fnx-python/src/readwrite.rs (registered in that module's own
register(); no lib.rs edit) builds `{u: [v,...]}` with adjacency-order neighbor
lists via `inner.neighbors_iter`, bypassing the slow per-node G.neighbors()
AdjacencyView loop. Python wrapper gates on `nodelist is None and type(G) is
Graph` (exact; excludes DiGraph/Multi/subclasses/SubgraphViews); nodelist use
takes the unchanged general path.

Isomorphism: list order = neighbors_iter order = nx adjacency order (0 mismatches
across 5 BA graphs incl node order + list order); self-loops yield u once;
returns Python list. Golden:

    TDOL_GOLDEN 8933c83e74c9bf74181ffc5bb94effd15250af0b6d677dfd393ba6ea6bc6ccff

16 dict/convert pytest cases + clippy -D warnings pass.

Bench (BA(1500,4), median/9): 9.81ms -> 0.728ms = 13.5x; now FASTER than nx (1.115ms).
Opportunity Score = Impact 4 x Confidence 5 / Effort 1 = 20.
