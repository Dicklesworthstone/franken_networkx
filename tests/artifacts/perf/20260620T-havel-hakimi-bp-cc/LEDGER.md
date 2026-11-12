# Perf WIN (code-only) — bipartite havel_hakimi_graph de-delegation (br-r37-c1-bphhgen)

- Agent: `BlackThrush` · 2026-06-20 · File: `python/franken_networkx/bipartite.py`
- DISK-LOW turn: code-only, NO cargo. Parity + conformance via existing install.

`bipartite.havel_hakimi_graph` delegated (build nx MultiGraph per-edge via the
Havel-Hakimi loop, then _from_nx_graph convert — the slow String-keyed multigraph
substrate twice). De-delegate the default (create_using None -> MultiGraph): run nx's
deterministic Havel-Hakimi loop VERBATIM to collect edges in nx's exact order
(largest-a-degree node -> largest-b-degree stubs, in-place stub decrement/remove),
then one bulk add_edges_from. Node labels, bipartite tags, multi-edge KEY order, the
suma!=sumb NetworkXError, and the graph name (set only when edges exist — matching
nx's early return) are byte-identical.

## Parity (existing install, no build)
- 4000 random valid bipartite degree-sequence pairs: byte-exact node order, edge order
  WITH multigraph keys, bipartite attrs, graph name, MultiGraph type. 0 mismatches,
  0 error-contract mismatches.
- invalid (sum mismatch) -> NetworkXError matches; empty -> no name (matches early
  return); pytest -k 'havel or bipartite': 1305 passed, 78 skipped.

## Perf
BENCH DEFERRED (disk-low). Win = skip nx MultiGraph build + _from_nx_graph conversion
(both on the slow String-keyed multigraph substrate). Measure when disk recovers.

## Follow-up
alternating_havel_hakimi_graph + reverse_havel_hakimi_graph (same deterministic
degree-sequence family, MultiGraph default) — replicable next.
