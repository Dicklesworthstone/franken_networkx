# Perf lever (code-only, bench deferred) — threshold_graph native build (br-r37-c1-threshnative)

- Agent: `BlackThrush` · 2026-06-20 · File: `python/franken_networkx/threshold.py`
- DISK-LOW turn: code-only, no build/bench. Parity verified with existing install.

`threshold.threshold_graph(creation_sequence)` delegated: build an intermediate
networkx graph (per-edge add_edge over the O(V^2) dominating edges) THEN pay
_from_nx_graph (fnx<-nx conversion + adjacency-row alignment).

Lever: for the default (create_using is None -> fnx.Graph) build DIRECTLY,
replicating nx's exact algorithm verbatim — same creation-sequence parsing
(string / labeled-tuple / compact via nx's own uncompact), same "dominating node
connects to all existing nodes in node order" edge emission, same node order, same
graph name — then build via one add_nodes_from + one batched add_edges_from. Skips
the per-edge nx construction AND the conversion (the from_* double-build lever
[[reference_from_nx_graph_double_build]]). A non-None create_using keeps delegation.

## Parity (existing install, no build)

2000 random creation sequences across ALL 3 formats (string ['d','i'...],
labeled-tuple [(node,'d')...], compact [int...]): byte-exact node order, edge order,
graph attrs (name="Threshold Graph"), returns fnx.Graph; error contract matches.
The 3 docstring examples match. 0 mismatches.

## Perf

BENCH DEFERRED (disk-low). Confident win (skip nx build + _from_nx_graph + per-edge
add_edge construction). Measure when disk recovers.
