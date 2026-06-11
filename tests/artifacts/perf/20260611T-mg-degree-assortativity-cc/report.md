# perf: degree_assortativity_coefficient (MultiGraph) — in-process, no conversion

Bead: br-r37-c1-6pdq6. MultiGraph degree_assortativity delegated to nx; cProfile
showed 98% of the 542ms was the _fnx_to_nx MULTIGRAPH conversion (_align_rows +
_topo_emit_edges_by_adj via per-edge AtlasView access) — the nx algorithm itself is
~2ms. 542ms vs 2.26ms = 239x slower (n=200 MultiGraph).

## Lever (ONE)
degree_assortativity is an order-invariant scalar, so reproduce nx's EXACT pipeline
in-process on the fnx graph: build the degree-pair iterator with nx's node_degree_xy
semantics from FAST BULK reads — dict(G.degree()) + list(G.edges()) (both native;
the per-node G.edges(u) round-trips are what made even an in-process port slow) —
then feed nx's own mixing_dict / dict_to_numpy_array / _numeric_ac (graph-agnostic
numpy) so the float result is byte-identical. Gated to the default contract
(x=out, y=in, nodes=None) and weight=None: unweighted degrees are exact integers so
the result matches nx bit-for-bit. Weighted multigraphs STAY delegated (the weighted
degree is a float sum whose accumulation order diverges -> directed weighted differs
in the last ULPs, not byte-exact).

## Proof (byte-exact)
- Golden over 8 cases x {weight=None, weight='weight'} (undir/dir +/- self-loops,
  empty, cycle=NaN, parallel-only) compares repr() (exact bit pattern, incl NaN) of
  fnx vs nx — all equal. SHA 8653a5dcf6f652c5f9bfba1524457d5ba80026dcd9bd0634198e33e01f1ffe57
- Focused pytest (assortativity/mixing/degree_pearson): 601 passed.

## Benchmark (MultiGraph n=200, ~400 edges, min-of-20)
| metric      | value                  |
|-------------|------------------------|
| nx          | 2.04 ms                |
| fnx before  | 542 ms (239x slower)   |
| fnx after   | 0.96 ms (2.1x faster)  |

~560x self-speedup; 239x-slower-than-nx -> 2.1x faster, byte-exact. Pure-Python.
