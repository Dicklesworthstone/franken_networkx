# Perf WIN (code-only) — complete_bipartite_graph de-delegation (br-r37-c1-bpcompletegen)

- Agent: `BlackThrush` · 2026-06-20 · File: `python/franken_networkx/bipartite.py`
- DISK-CRITICAL turn: code-only, NO cargo. Parity + conformance via existing install.

`bipartite.complete_bipartite_graph` delegated: build an nx graph (per-edge add over
the O(n1*n2) complete-bipartite edges) THEN _from_nx_graph convert. De-delegate the
common integer case (create_using None -> fnx.Graph): replicate nx's post-
nodes_or_number behaviour verbatim — top=range(n1), bottom=[n1+i for i in range(n2)],
bipartite 0/1 tags, all top x bottom edges, graph name
"complete_bipartite_graph(n1, n2)" — and build via add_nodes_from + add_edges_from.
Containers / create_using keep the delegation path (nodes_or_number + type semantics).

## Parity (existing install, no build)
- integer case all (n1,n2) in 0..24: 625/625 byte-exact (node order, edge order,
  bipartite attrs, graph name, fnx.Graph type).
- container case still delegates correctly; pytest -k bipartite: 1116 passed, 78 skipped.

## Perf
BENCH DEFERRED (disk-critical). Win = skip nx build + _from_nx_graph + per-edge add
for the O(n1*n2) edges. Measure when disk recovers.

## Follow-up — other bipartite generators
DETERMINISTIC (byte-exact-replicable): havel_hakimi_graph, alternating_havel_hakimi_graph,
reverse_havel_hakimi_graph (degree-sequence constructors). RNG ones (random_graph,
gnmk_random_graph, configuration_model, preferential_attachment_graph) need nx
PythonRandom draw-sequence replication (reference_native_directed_generator_pythonrandom).
