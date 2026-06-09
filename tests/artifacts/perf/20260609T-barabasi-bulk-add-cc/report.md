# barabasi_albert_graph: single bulk add_edges_from — 2.30x slower -> 1.09x (near parity) (br-r37-c1-bagen)

## Problem
The BA wrapper called graph.add_edges_from(...) ONCE PER STEP (~n-m small native
binding round-trips). Profiling (release, n=1500 m=4) showed add_edges_from (binding
+ Python wrapper) was the dominant cost. 2.30x slower than nx; build-independent
construction tax. (BA is parity-blocked at the native generator level — its RNG
differs from nx's — so the algorithm must stay in Python.)

## Lever
The BA loop never READS the graph (degree state lives entirely in repeated_nodes),
so accumulate every edge into a list and add them in a SINGLE add_edges_from at the
end. Edge + node insertion order is preserved (sources processed in increasing
order), so the graph is byte-identical to nx's incremental build.

## Proof
- Parity vs nx 0/320 (40 seeds x m{1,2,4,7} x n{30,100}): exact node order + edge
  set; initial_graph variant matches; pytest -k barabasi/generator 1055 passed.
- RELEASE n=1500 m=4 (min-of-15): 2.30x slower -> 1.09x; n=5000 m=5: 1.23x.
