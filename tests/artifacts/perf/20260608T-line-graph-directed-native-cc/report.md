# line_graph (directed): native fast path (br-r37-c1-lgnative)

## Problem
`line_graph` builds L(G) whose NODES are G's edges, represented as Python tuples
`(u, v)`. The Python path adds each L-node/edge one PyO3 call at a time and
re-canonicalizes both tuple endpoints on every L-edge (the tuple-key
construction tax). Measured: directed 3.26x slower, undirected 1.95x slower.

## Lever (ONE) — directed only
Native `line_graph_fast`: canonicalize each L-node tuple `(u,v)` EXACTLY ONCE,
then assemble the directed L-edges `(u,v)->(v,w)` in pure Rust by integer edge
index over the source CSR adjacency (successors_indices), bulk-insert via
extend_*_unrecorded, build the PyDiGraph zero-copy. Directed L-edge orientation
is intrinsic (from-edge -> to-edge), so the result is byte-identical to nx.

## Parity-blocked: undirected
The UNDIRECTED case is NOT routed to the kernel. nx orients each undirected
L-edge by the result's node-INSERTION order, which derives from CPython
set-iteration order of the internal edge set (see networkx line_graph). That
order is unmatchable without replicating nx's exact Python construction
(orientation-sensitive `sorted(edges())` diverged 23/40). Undirected stays on
the Python path that mirrors nx. (Class: parity-blocked-by-set-order.)

## Proof (behavior parity — absolute)
- 70 line_graphs (directed/undirected x attrs/self-loops/multigraph; native +
  fallback paths): 0 mismatches on class, node-set, node-DATA, and
  orientation-sensitive edge list.
- Golden directed+undirected fnx == nx.
- `pytest -k line_graph`: 25 passed (incl. the orientation-sensitive
  test_parity_conformance::test_line_graph).

## Result (median-of-4, directed)
| n, m       | nx       | fnx (after) | speedup vs nx | self-speedup |
|------------|----------|-------------|---------------|--------------|
| 600, 3000  | 25.04 ms | 20.40 ms    | 1.23x         | 84.9->20.4ms (4.2x) |
| 800, 5000  | 54.25 ms | 38.87 ms    | 1.40x         |              |

Before: directed 3.26x SLOWER than nx. After: 1.2-1.4x faster (4.2x self-speedup).
