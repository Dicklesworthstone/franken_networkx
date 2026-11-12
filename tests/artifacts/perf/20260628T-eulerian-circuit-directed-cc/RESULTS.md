# eulerian_circuit directed de-delegation — CopperCliff 2026-06-28

## Problem
Directed simple eulerian_circuit still paid fnx->nx conversion + nx Hierholzer => 0.64x.
(Undirected was already de-delegated.)

## Fix (pure Python, __init__.py, br-cc-eulcircdir)
nx directed path: G = G.reverse() then Hierholzer over reversed OUT-edges (yields forward edges).
In-process: build rev_succ[v] = sources u of arcs (u,v) in G.edges() order, run identical stack walk.
Byte-exact because reverse() builds _succ[v] in G.edges() order == rev_succ construction (no second-direction reinsertion).

## Measured
directed cycle: n=200 11.5x, n=800 13.0x ; complete digraph m=40/80 12.2-12.7x  (was 0.64x)

## Correctness
- 0/1840 adversarial == nx (cycles, complete digraphs, unions of 3-8 random cycles/6-30 nodes, 3 sources) + selfloops + non-eulerian->NetworkXError
- 603 euler conformance tests pass

## Observation (NO-SHIP)
Pre-existing UNDIRECTED de-delegation is NOT byte-exact vs nx (uses G.adjacency() order; nx uses G.copy()._adj order). Benign: valid circuits, all conformance passes. Not fixed.
