# k_truss: native kernel + rebuild instead of fnx->nx delegation (br-r37-c1-jboes)

k_truss DELEGATED to networkx via the heavy _fnx_to_nx conversion (topo-emit edge
ordering + attribute copy on input, plus _from_nx_graph on output) -- the two
conversions dominated, making it ~2.9x SLOWER than networkx (n=1000: ~69ms vs
~24ms). The native k_truss_rust kernel already exists but was abandoned
(br-r37-c1-3qopf) because it returned nodes in sort order rather than nx's input
order.

Lever: call k_truss_rust (computes the k-truss node/edge SETS directly on the fnx
adjacency, no conversion) and rebuild the result subgraph by iterating G's own
nodes/edges -- restoring nx's exact node / edge / adjacency order AND preserving
node / edge / graph attributes. The k-truss is a fixpoint (order-independent set),
so the only thing the delegation bought -- output ordering -- is recovered by the
rebuild.

Proof: byte-identical to networkx (nodes, edges, adjacency iteration, node/edge/
graph attrs) over 300 graphs x k in {2..7} = 1800/1800 (incl string nodes +
attributes); golden sha256; 11 existing k_truss + 289 core tests pass.

| n | nx (ms) | fnx before (delegate) | fnx after (native) |
|---|---|---|---|
| 400 | 10.35 | ~16-22 | 10.21 (1.01x) |
| 1000 | 19.6-24.7 | ~69 (0.36x) | 23.8 (~parity) |

before: ~2.9x SLOWER than nx (two fnx<->nx conversions).
after:  at parity with nx (0.82-1.01x); 1.6-2.9x faster than the delegation.
        No conversion -- the native triangle kernel runs on fnx adjacency directly.
