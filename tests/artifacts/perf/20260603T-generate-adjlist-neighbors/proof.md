# generate_adjlist simple-graph fast path (br-r37-c1-genadj)

## Root cause
`generate_adjlist(G)` (python/franken_networkx/readwrite/__init__.py) iterated
`G.adjacency()`, which for every node materialises the full `{nbr: attrs}` dict
by walking the AtlasView lambda chain — but the function only consumes the
neighbour KEYS. ~7x (undirected) / ~11x (directed) slower than networkx.

## Lever
For simple (non-multi) graphs, iterate `G.neighbors(node)` directly (native
accessor, neighbour keys in adjacency order, no attr-dict materialisation).
Multigraphs keep the existing `G.adjacency()` path unchanged: nx's
generate_adjlist expands parallel edges (a neighbour appears once per parallel
edge), which a simple neighbour list does not capture (that multigraph path is
a separate pre-existing parity matter, not touched here).

## Isomorphism
Byte-identical output verified vs networkx across Graph + DiGraph x 4 seeds x
self-loops on/off x delimiters {" ", ","} x subgraph views, plus write_adjlist
round-trip body parity:

    mismatches=0
    GENADJ_GOLDEN e3cb0966020830c186eaba6baf5f7159208429c9bf2cda9bb26b85b25cb358a2

141 adjlist/readwrite/edgelist pytest cases pass (the 1 unrelated failure,
test_to_edgelist_view_type, is pre-existing on HEAD — fails with this change
stashed too).

## Benchmark (generate_adjlist over a 900-edge graph on 300 nodes, median)

    Graph    before: 6.932 ms   after: 0.990 ms   -> 7.0x
    DiGraph  before: 5.274 ms   after: 0.479 ms   -> 11.0x

Opportunity Score = Impact 4 x Confidence 5 / Effort 1 = 20. Pure-Python,
collision-free (unreserved submodule), no Rust change.

## Note
Bead br-r37-c1-genadj not yet filed: .beads/issues.jsonl is reserved by
TealSpring (active). File once released.
