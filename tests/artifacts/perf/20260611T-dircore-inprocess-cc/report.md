# perf: core_number(directed) — in-process Batagelj-Zaversnik (de-delegate)

Bead: br-r37-c1-4i0ad. Directed core_number delegated to nx (native kernel
collapses antiparallel arcs to undirected, halving degree), paying the full
fnx->nx conversion (~2ms at n=250 = ~6x slower than nx). Also paid by every
directed k_core/k_shell/k_crust/k_corona (they route through core_number).

## Lever (ONE)
De-delegate: reproduce nx's exact Batagelj-Zaversnik core decomposition in-process
on the fnx graph (degree = in+out, antiparallel counted twice; all_neighbors =
predecessors ++ successors). The k-core number is a UNIQUE graph invariant, so the
output is byte-exact regardless of tie-break order. Adjacency read via native
_native_predecessor_row_dict / _native_successor_row_dict (identical order to the
public API, far cheaper); nx-typed graphs fall back to G.predecessors/successors.

## Proof (byte-exact)
- Golden SHA over 7 directed graphs (sparse/dense gnp, gn tree, scale-free with
  antiparallel, directed cycle, fully-bidirectional K25, disconnected+isolates):
  35e96d3ee1089e727b8c459c42a5a56bb9b5f242480ed32f0dad843409e70a94
- Output dict values AND key order match nx exactly. Self-loop inputs raise the
  same NetworkXNotImplemented. Parity re-verified at n=1000 and n=2000.
- Focused pytest (core_number/k_core/k_shell/k_crust/k_corona/onion): 494 passed.

## Benchmark (directed gnp)
| n    | nx (ms) | fnx before (ms) | fnx after (ms) | before vs nx | after vs nx |
|------|---------|-----------------|----------------|--------------|-------------|
| 250  | 0.43    | 2.64            | 0.39           | 6.0x slower  | 1.1x faster |
| 1000 | 3.75    | —               | 3.25           | —            | 1.15x faster|
| 2000 | 8.39    | —               | 7.12           | —            | 1.18x faster|

~6.8x self-speedup at n=250 (conversion tax removed); 6x-slower -> faster than nx,
byte-exact. Pure-Python (no rebuild).
