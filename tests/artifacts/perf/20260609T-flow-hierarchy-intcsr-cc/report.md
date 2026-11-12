# flow_hierarchy: integer-CSR Tarjan + integer edge scan — 5x slower -> 30x FASTER + self-loop bug fix (br-r37-c1-flowhier)

## Problem
flow_hierarchy(unweighted) routed to native flow_hierarchy_directed but was ~5x
SLOWER than nx. The kernel paid the String-adjacency tax twice: Tarjan's DFS
called successors(name) (allocates a Vec<&str> per node) + idx.get String lookup
per edge, and the cycle-edge counting loop ran over edges_ordered() (clones EVERY
edge's endpoints + AttrMap) with another idx.get per edge.

## Lever
Walk the integer out-adjacency directly: Tarjan over successors_indices(v) ->
&[usize] (no alloc, no String map) and count cycle edges by scanning
successors_indices(u) for scc_id[u]==scc_id[v]. O(|V|+|E|), zero String work,
zero edge clones.

## Correctness bonus
Fixed a latent self-loop divergence: nx counts an edge "in a cycle" iff both
endpoints share an SCC (== sum over SCCs of subgraph.size()), INCLUDING a self-loop
on a singleton SCC. The old `scc_sizes > 1` guard dropped those, so a self-loop on
a 1-node SCC was wrongly treated as acyclic. New code matches nx exactly.

## Proof
- Parity vs nx 0/360 (60 seeds x self-loops{F,T} x deg{2,4,8}); DAG=1.0, full
  cycle=0.0, self-loop case fnx=0.5==nx (old kernel gave 1.0); golden sha
  61b869c8811297db; pytest -k flow_hierarchy 26 passed.
- Speed n=2000 deg6 (min-of-12): fnx 0.425ms vs nx 12.915ms = 0.03x = 30.4x FASTER.
