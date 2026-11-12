# Perf WIN (code-only) — alternating/reverse_havel_hakimi_graph de-delegation (br-r37-c1-bphhgen)

- Agent: `BlackThrush` · 2026-06-20 · File: `python/franken_networkx/bipartite.py`
- DISK-LOW turn: code-only, NO cargo. Parity + conformance via existing install.

Follow-up to havel_hakimi_graph (br-r37-c1-bphhgen). Same lever for the two variants
(default create_using None -> MultiGraph): run nx's deterministic loop verbatim to
collect edges in nx's exact order, then one bulk add_edges_from, skipping the nx
MultiGraph build + _from_nx_graph conversion (slow String-keyed substrate twice).
- alternating: largest-a-degree -> b-stubs interleaved low/high via zip(large, small)
  with the zip-truncation large.pop() fixup.
- reverse: largest-a-degree -> SMALLEST-degree b-stubs (bstubs[0:degree], sorted once).
Node labels, bipartite tags, multi-edge keys, suma!=sumb NetworkXError, and the
graph name (set only when edges exist) are byte-identical.

## Parity (existing install, no build)
- alternating_havel_hakimi_graph: 4000/4000 byte-exact (node/edge order WITH keys,
  bipartite attrs, graph name, MultiGraph type), 0 error-contract mismatches.
- reverse_havel_hakimi_graph: 4000/4000 byte-exact.
- pytest -k 'havel or bipartite': 1305 passed, 78 skipped.

## Perf
BENCH DEFERRED (disk-low). Win = skip nx MultiGraph build + _from_nx_graph conversion.
Measure when disk recovers.

## Bipartite generator status
DETERMINISTIC family DONE: complete_bipartite_graph, havel_hakimi_graph,
alternating_havel_hakimi_graph, reverse_havel_hakimi_graph. Remaining = RNG generators
(random_graph, gnmk_random_graph, configuration_model, preferential_attachment_graph)
needing nx PythonRandom draw-sequence replication.
