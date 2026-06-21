# Perf WIN + correctness fix (code-only) — contracted_* skip redundant _from_nx_graph (br-r37-c1-contractnoconv)

- Agent: `BlackThrush` · 2026-06-20 · File: `python/franken_networkx/minors.py`
- DISK-LOW turn: code-only, no build. Parity + conformance verified with existing install.

`contracted_nodes` / `contracted_edge` / `identified_nodes` (all via
`_convert_contraction_result`) ran `nx.contracted_*(G)` then `_from_nx_graph(result)`
for copy=True. But nx's contraction does `H = G.copy()`, and fnx's `.copy()` is an
fnx graph — so the result is ALREADY an fnx graph, byte-identical to nx-on-an-nx-graph.

The `_from_nx_graph` step was therefore (a) a redundant O(V+E) re-conversion AND
(b) a CORRECTNESS BUG: the fnx->nx->fnx round-trip of the nested `contraction`
edge-attr record DIVERGED from nx. Verified: of 1000 random contractions, 215 had
the DIRECT result match nx-on-nx while the re-converted one did NOT; 0 the other way.

Fix: return the already-fnx result directly (gated on isinstance fnx graph; genuine
nx-typed inputs still convert).

## Parity (existing install, no build) — return-direct vs nx-on-an-nx-graph
- contracted_nodes 1500/1500, identified_nodes 1500/1500, contracted_edge 1000/1000
  (all 4 graph types, self_loops on/off; full: node order, edges+keys, node/edge
  attrs incl the contraction record, graph attrs).
- pytest -k 'contract or minor or quotient or identified': 797 passed.

## Perf
BENCH DEFERRED (disk-low). Win = skip the whole _from_nx_graph conversion per call.
Measure when disk recovers. (Also fixes a real correctness divergence — ship now.)
