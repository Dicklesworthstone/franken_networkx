# bipartite.degrees — concrete in-process override (de-dispatch)

## Lever
fnx.bipartite does `from networkx.algorithms.bipartite import *`, so `degrees`
was nx's @nx._dispatchable version. Calling it on an fnx graph round-tripped the
WHOLE graph through _fnx_to_nx (full O(V+E) conversion, profiled 0.328s cumtime /
200 calls) just to build two lazy DegreeViews — 62x slower than nx. Added a
concrete degrees() running nx's exact algorithm directly on the fnx graph
((B.degree(B-nodes, weight), B.degree(nodes, weight))) — no conversion. Same
override pattern as density/degree_centrality (br-r37-c1-bipdense).

## Correctness
24 cases (gnmk bipartite x weight {None,'weight'}): both DegreeViews' values AND
node key order identical to nx, 0 mismatches. golden 6c5a7beb. 441 bipartite tests
pass.

## Benchmark (warm min, interleaved before/after)
| op                | BEFORE    | AFTER     | self-speedup |
|-------------------|-----------|-----------|--------------|
| degrees(construct)| 0.7572ms  | 0.0305ms  | 24.8x        |
| degrees+materialize| 0.7704ms | 0.0529ms  | 14.6x        |

62x slower -> ~parity with nx (nx ~0.031ms). The conversion trap is eliminated.
