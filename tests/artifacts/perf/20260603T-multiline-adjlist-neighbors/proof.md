# generate_multiline_adjlist simple-graph fast path (br-r37-c1-genadj)

## Root cause
`generate_multiline_adjlist(G)` (readwrite submodule) iterated `G.adjacency()`,
materialising `dict(self.adj[node])` per node via the AtlasView lambda chain.
~4.5x (undirected) / ~3.8x (directed) slower than networkx.

## Lever
Simple (non-multi) path: take neighbour keys from native `G.neighbors(node)`
(adjacency order) and the per-edge data dict from native `G.get_edge_data(node,
nbr)` — no AtlasView dict materialisation. Multigraph path unchanged.

## Isomorphism
Byte-identical vs networkx across Graph + DiGraph x 4 seeds x self-loops on/off
x edge-attr mixes x delimiters {" ", "|"} x subgraph views, plus
write_multiline_adjlist round-trip body:

    mismatches=0
    MLADJ_GOLDEN a28f318f406bbbb9b14066d8192d2a2c979733e7f2d687ccf13d9096d7ff013c

99 adjlist/multiline/readwrite pytest cases pass.

## Benchmark (generate_multiline_adjlist over a 900-edge graph, median)

    Graph    before: 8.901 ms   after: 1.958 ms   -> 4.5x
    DiGraph  before: 6.916 ms   after: 1.801 ms   -> 3.8x

Opportunity Score = Impact 4 x Confidence 5 / Effort 1 = 20. Pure-Python,
collision-free (unreserved submodule). Sibling of the generate_adjlist fast
path (5ed019501). Bead filing deferred (.beads reserved by TealSpring).
