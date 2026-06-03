# br-r37-c1-0nkch Isomorphism Proof

## Candidate Surface

The rejected candidate changed only the exact simple-Graph branch of:

- `franken_networkx.ego_graph(G, n, radius=2, center=True, undirected=False, distance=None)`.

All other branches were gated to the existing Python implementation.

## Behavior Obligations

- Node ordering: candidate added result nodes in source `G.nodes()` insertion order, matching `G.subgraph(sp).copy()`.
- Edge ordering and orientation: candidate scanned source edge iteration order and inserted the same public endpoint orientation.
- Tie-breaking: BFS discovery used the source native neighbor index order; the result order still came from source node order, as in NetworkX.
- Attributes: graph, node, and edge attribute dicts were shallow-copied into the result graph.
- Floating point: not involved in the unweighted exact branch.
- RNG: not involved.

## Golden Output

NetworkX, baseline FNX, after-candidate FNX, and restored FNX all produced:

`a66fe1d2d36fe1f69a5966fab6d739d8b5b34ed0aae622b17565fbba8ce603d6`

## Validation

- Focused parity after candidate: `14 passed in 0.52s`.
- Focused parity after source restoration: `13 passed in 0.59s`.
- Restored sample retained the same golden digest.

## Verdict

Behavior was isomorphic, but performance regressed. Candidate code was removed.
