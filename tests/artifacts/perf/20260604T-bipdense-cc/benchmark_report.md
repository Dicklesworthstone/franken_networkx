# bipartite density / degree_centrality: native override (br-r37-c1-bipdense)

fnx.bipartite re-exports networkx's `@nx._dispatchable` functions. For TRIVIAL
ones -- density (an O(1) formula) and degree_centrality (an O(V) degree sum) --
calling them on an fnx graph paid ~4ms of networkx dispatch + substrate overhead,
the entire cost. density was ~80x SLOWER and degree_centrality ~100x SLOWER than
networkx, purely from the dispatch machinery.

Lever: override both with networkx's exact formula computed directly on the fnx
graph (no nx dispatch, no conversion). density = m/(nb*nt) [2*nb*nt directed];
degree_centrality reproduces nx's exact top/bottom scaling and dict key order.
Both work on fnx AND nx inputs.

Proof: byte-identical to networkx (values + dict key order) over 250 graphs incl
nx-typed input, directed bipartite, empty graph (1008/1008); golden sha256; 429
existing bipartite tests pass.

| fn | nx | current (nx-on-fnx) | override |
|---|---|---|---|
| density | 0.041ms | ~4.05ms | 0.0017ms (23.7x FASTER than nx) |
| degree_centrality | 0.081ms | ~4.08ms | 0.245ms (17x faster than current) |

before: density ~80x SLOWER, degree_centrality ~100x SLOWER than nx (dispatch tax).
after:  density 23.7x FASTER than nx; degree_centrality 17x faster than current
        (3x slower than nx -- the residual G.degree() substrate cost).
