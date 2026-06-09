# is_regular: native O(V) integer degree-equality — 50x slower -> 4-34x FASTER (br-r37-c1-regidx)

## Problem
is_regular was a pure-Python wrapper iterating the whole DegreeView
(`all(d0 == d for _, d in G.degree)`) — a per-node PyO3 round-trip through the view.
An undirected native binding existed but (a) the wrapper never called it and (b) it
was `require_undirected` (errored on DiGraph) and used String node_degree. 50x slower
than nx (build-independent: it's the DegreeView dispatch, not the algorithm).

## Lever
Native binding using integer degree_by_index / in/out_degree_by_index (O(1)/node,
short-circuit): undirected = all nodes one degree; directed = all one in-degree AND
one out-degree (nx's definition). Wrapper routes simple Graph/DiGraph to it;
multigraphs (parallel-edge degree multiplicity) stay on the Python degree-view path.

## Proof
- Parity vs nx 0/69 (random/regular x directed/undirected; cycle/complete/star/path/
  dicycle; self-loops; string nodes; single node; MULTIGRAPH fallback; empty raises
  NetworkXPointlessConcept); pytest -k regular 185 passed.
- RELEASE n=5000 (min-of-20): irregular deg8 50x slower -> 0.25x (4x FASTER);
  regular cycle (full scan) -> 34x FASTER (0.0135ms vs nx 0.465ms).
