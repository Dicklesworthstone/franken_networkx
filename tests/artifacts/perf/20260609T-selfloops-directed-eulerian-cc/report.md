# number_of_selfloops(DiGraph) O(V+E)->O(V) + is_eulerian directed parity (br-r37-c1-selfloopdir/euleridx)

## Problem
number_of_selfloops(G) on a DiGraph was ~24ms at 3600 edges (270x slower than nx)
because nodes_with_selfloops_rust called gr.undirected() — building the WHOLE
O(|V|+|E|) undirected projection of the digraph just to find self-loops. It has
many internal callers; e.g. is_eulerian's self-loop guard, making is_eulerian on a
DiGraph 3532x SLOWER than nx (which never checks self-loops at all).

## Levers
1. nodes_with_selfloops_rust: GraphRef::Directed fast path — scan the digraph's own
   (i,i) edges via edge_attrs_by_indices in O(|V|), node-insertion order. No
   undirected projection. (24ms -> 0.54ms, 44x.)
2. is_eulerian binding: integer in/out-degree (successors_indices/
   predecessors_indices slice lengths, O(1)/node) instead of dg.in_degree(name).
3. is_eulerian wrapper: gate the self-loop guard on `not G.is_directed()` — the
   directed native path (degree balance + is_strongly_connected) already matches nx
   on self-loops (verified 0/66), so directed skips number_of_selfloops entirely.

## Proof
- selfloop family (number_of_selfloops + nodes_with_selfloops + selfloop_edges)
  parity 0/960 directed+undirected; directed binding vs nx on self-loop graphs
  0/66; is_eulerian FULL parity 0/303; pytest -k eulerian/selfloop 922 passed.
- number_of_selfloops DiGraph n=2000 deg8: 24ms-class -> 0.54ms (44x). is_eulerian
  DiGraph not-eulerian n=2000: 3532x slower -> 0.96x (PARITY).
