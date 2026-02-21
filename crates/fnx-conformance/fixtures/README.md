# Conformance Fixtures

This folder stores normalized oracle-vs-target fixtures for fnx-conformance.

- `graph_core_shortest_path_strict.json`: deterministic graph mutation + unweighted shortest path parity in strict mode.
- `graph_core_mutation_hardened.json`: graph mutation and attribute-merge parity in hardened mode.
- `smoke_case.json`: minimal bootstrap fixture retained for harness wiring metadata.
- `generated/dispatch_route_strict.json`: dispatch backend selection and action parity.
- `generated/convert_edge_list_strict.json`: conversion-route graph parity.
- `generated/readwrite_roundtrip_strict.json`: read/write round-trip parity.
- `generated/readwrite_hardened_malformed.json`: hardened malformed-input behavior parity.
- `generated/view_neighbors_strict.json`: live view neighbor ordering parity.
- `generated/readwrite_json_roundtrip_strict.json`: JSON read/write + view parity.
- `generated/components_connected_strict.json`: connected-components + component-count parity.
- `generated/generators_path_strict.json`: deterministic `path_graph` generator parity.
- `generated/generators_star_strict.json`: deterministic `star_graph` generator parity.
- `generated/generators_cycle_strict.json`: deterministic `cycle_graph` generator parity.
- `generated/generators_complete_strict.json`: deterministic `complete_graph` generator parity.
- `generated/centrality_degree_strict.json`: deterministic degree-centrality parity.
- `generated/centrality_betweenness_strict.json`: deterministic betweenness-centrality parity.
- `generated/centrality_edge_betweenness_strict.json`: deterministic edge-betweenness-centrality parity.
- `generated/centrality_closeness_strict.json`: deterministic closeness-centrality parity.
- `generated/centrality_harmonic_strict.json`: deterministic harmonic-centrality parity.
- `generated/centrality_katz_strict.json`: deterministic Katz-centrality parity.
- `generated/centrality_hits_strict.json`: deterministic HITS hubs/authorities parity.
- `generated/centrality_pagerank_strict.json`: deterministic PageRank parity.
- `generated/centrality_eigenvector_strict.json`: deterministic eigenvector-centrality parity.
