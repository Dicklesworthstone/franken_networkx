# perf: min_cost_flow/network_simplex — in-process network-simplex port + fast extraction

Bead: br-r37-c1-8foqi. After 6f176b3cd, min_cost_flow ran nx's network_simplex via
`__wrapped__` ON the fnx graph (the algorithm's repeated G.edges/G.nodes/selfloop_edges
reads paid the per-element AdjacencyView tax = ~2x slower than nx). Profiling showed the
graph I/O — not the simplex pivots — was the gap, plus redundant Python pre-validation +
`_mcf_inputs_all_integral` re-walks (78k slow numbers.Integral ABC checks).

## Lever (ONE)
Port nx's primal network-simplex (BSD) into `_network_simplex_native.py` (pivot logic
verbatim) and run it over a `_FastG` shim that pre-extracts the node/edge data ONCE via
fnx's native bulk readers (`nodes(data=True)` / `_native_edges_with_data`); the algorithm's
repeated graph reads become plain list/dict lookups. Reuse the same _FastG for the
pre-validation and the integral-check (fast `type(x) is int` path), eliminating ~4
redundant whole-graph passes. Cost-exact by construction (conformance contract is cost-only).

## Proof (cost-exact)
- Golden over a 5-graph demand corpus: min_cost_flow_cost==nx, total flow balance==nx,
  fnx flow is a valid optimum, network_simplex cost==nx. SHA unchanged: MCF_GOLDEN_SHA=e335234edfb42ea82f6168ea8817a990d31e09d25d79376a427ee1fb62abe051
- 1072 flow / min_cost / network_simplex / capacity_scaling / error_message tests pass.

## Benchmark (gnp directed, real demands, interleaved min-of-12)
| n    | nx (ms) | fnx start-of-session | fnx after | start vs nx | after vs nx |
|------|---------|----------------------|-----------|-------------|-------------|
| 300  | 12.1    | ~22.9 (2.05x)        | 15.4      | 2.05x slow  | 1.27x slow  |
| 600  | 34.3    | ~68 (2.04x)          | 41.7      | 2.04x slow  | 1.22x slow  |
| 1000 | 49.8    | —                    | 64.6      | —           | 1.30x slow  |

The network-simplex SOLVER itself (ported, on _FastG) is true parity (1.03-1.10x vs nx);
the residual ~1.25x on min_cost_flow is the cost_of_flow + remaining validation passes.
Total journey (with 6f176b3cd): SSP 50-96x slower -> ~1.25x. Pure-Python, BSD port.
NEXT: native Rust pivots to BEAT nx (the pivots are the only Python-bound remainder).
MCF_GOLDEN_SHA=e335234edfb42ea82f6168ea8817a990d31e09d25d79376a427ee1fb62abe051
