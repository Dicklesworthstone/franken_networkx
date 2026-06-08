# laplacian_centrality (directed): native in-process via native directed_laplacian_matrix (br-r37-c1-dirlapnative follow-up)

## Problem
laplacian_centrality computed the undirected case in-process but still DELEGATED
the directed case to nx (full fnx->nx conversion). That delegation existed only
because directed_laplacian_matrix wasn't native — now it is (06bb69f79).

## Lever (ONE)
Drop `G.is_directed()` from the delegate gate; pick the matrix source the way nx
does (directed -> native directed_laplacian_matrix(G, nodes, weight, walk_type,
alpha); undirected -> laplacian_matrix(...).toarray()), then the same numpy energy
loop. Callable weight still delegates. This also routes undirected MULTIgraph
through the native path (laplacian_matrix sums parallel edges, matching nx).

## Proof (correctness — no timing; host load avg ~12 this window)
- 1200 calls (directed/undirected x multigraph x weighted x strong x normalized
  T/F x walk_type random/lazy/pagerank): 0 mismatches (value + key order).
- Golden directed+undirected fnx == nx.
- `pytest -k laplacian`: 90 passed.

Structural delegation-elimination (load-independent).
