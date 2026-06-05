# perf: ego_graph O(E_subgraph) adjacency walk (was O(E_total) full edge scan)

Bead br-r37-c1-js9iw. Found via the small-output/large-graph sweep: ego_graph
was 19.9x slower than nx at n=2000.

## Lever
`ego_graph` is a pure-Python reimplementation (not delegated). After the BFS that
computes `nodes_within` (already O(E_subgraph)), it collected edges by
materializing **every** edge in G — `G.edges(data=True)` — and filtering by
membership: O(E_total). For an 18-node / 30-edge ego graph on a 6000-edge G that
scans 6000 edges (200x waste). networkx instead does `G.subgraph(sp).copy()`,
which walks only the subgraph nodes' adjacency: O(E_subgraph).

Replace the full-scan with a per-subgraph-node adjacency walk: iterate
`ordered_nodes` (already G-node order, the wrapper's contract), and for each its
`G[u]` adjacency; undirected edges dedup via a `seen` set so each edge is emitted
from the node encountered first — byte-identical to the previous
`G.edges()`-filter order (both are G-node-order EdgeView traversals restricted to
the subgraph). Directed graphs walk successors with no dedup. The non-string
attr-key special path and the `raw_add_edges_from` batching are preserved
verbatim. Multigraph branch left unchanged (correct; not the measured case).

## Correctness (isomorphism: NEW == OLD)
`isomorphism_proof.py`: 12000 configurations (150 random graphs x sources x
radius 1-4 x center T/F x undirected T/F for digraphs x weighted distance),
comparing node order + edge order + edge attrs + node attrs + graph attrs.
NEW working tree and OLD (git-stashed) produce an IDENTICAL sha:
`012ec7d217376ba9d601681ffa4fa538e7ee789607d4532539f9f8655173f6d7`.
24 ego pytest pass.

The change is behavior-preserving vs the committed wrapper. (A separate
pre-existing nx divergence in node order — nx's FilterAtlas uses CPython
set-iteration order when the subgraph is < half of G — is unaffected by this
change and tracked separately.)

## Perf (warm min-of-10, vs networkx)
- n=2000 r=2: OLD 22.51x -> NEW 3.34x  (self 3.349ms -> 0.474ms = 7.07x)
- n=5000 r=2: OLD 61.86x -> NEW 5.33x  (self 11.930ms -> 1.011ms = 11.80x)
- n=2000 r=3: OLD  9.96x -> NEW 2.12x  (self 4.122ms -> 0.871ms = 4.73x)

Complexity is now O(E_subgraph) matching nx; the residual 2-5x is the per-node/
edge PyO3 + Python-object construction tax (future native-subgraph kernel).
