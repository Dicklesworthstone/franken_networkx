# DOC-PASS-02 Symbol/API Census v1

Generated at: `2026-02-16T06:55:50.005530+00:00`
Baseline comparator: `legacy_networkx/main@python3.12`

## Census Summary
- workspace_crate_count: `10`
- symbol_count_total: `211`
- public_symbol_count: `191`
- internal_symbol_count: `20`
- high_regression_count: `131`

## Subsystem Families

| family | crates | public | internal | high-risk |
|---|---:|---:|---:|---:|
| algorithm-engine | 1 | 12 | 5 | 10 |
| compat-dispatch | 1 | 11 | 1 | 4 |
| conformance-harness | 1 | 9 | 2 | 11 |
| conversion-ingest | 1 | 15 | 0 | 3 |
| durability-repair | 1 | 11 | 4 | 11 |
| graph-generators | 1 | 12 | 0 | 0 |
| graph-storage | 1 | 29 | 4 | 13 |
| graph-view-api | 1 | 13 | 0 | 1 |
| io-serialization | 1 | 11 | 1 | 7 |
| runtime-policy | 1 | 68 | 3 | 71 |

## High-Regression Symbols (Top 25)

| symbol | crate | kind | visibility | module |
|---|---|---|---|---|
| ComponentsResult | fnx-algorithms | struct | public | `crates/fnx-algorithms/src/lib.rs:23` |
| NumberConnectedComponentsResult | fnx-algorithms | struct | public | `crates/fnx-algorithms/src/lib.rs:29` |
| bfs_shortest_path_uses_deterministic_neighbor_order | fnx-algorithms | fn | internal | `crates/fnx-algorithms/src/lib.rs:352` |
| connected_components | fnx-algorithms | fn | public | `crates/fnx-algorithms/src/lib.rs:135` |
| connected_components_are_deterministic_and_partitioned | fnx-algorithms | fn | internal | `crates/fnx-algorithms/src/lib.rs:376` |
| connected_components_include_isolated_nodes | fnx-algorithms | fn | internal | `crates/fnx-algorithms/src/lib.rs:394` |
| empty_graph_has_zero_components | fnx-algorithms | fn | internal | `crates/fnx-algorithms/src/lib.rs:410` |
| number_connected_components | fnx-algorithms | fn | public | `crates/fnx-algorithms/src/lib.rs:188` |
| number_connected_components_matches_components_len | fnx-algorithms | fn | internal | `crates/fnx-algorithms/src/lib.rs:420` |
| shortest_path_unweighted | fnx-algorithms | fn | public | `crates/fnx-algorithms/src/lib.rs:53` |
| add_edge | fnx-classes | fn | public | `crates/fnx-classes/src/lib.rs:217` |
| add_edge_autocreates_nodes_and_preserves_order | fnx-classes | fn | internal | `crates/fnx-classes/src/lib.rs:419` |
| add_edge_with_attrs | fnx-classes | fn | public | `crates/fnx-classes/src/lib.rs:225` |
| add_node | fnx-classes | fn | public | `crates/fnx-classes/src/lib.rs:172` |
| add_node_with_attrs | fnx-classes | fn | public | `crates/fnx-classes/src/lib.rs:176` |
| neighbor_count | fnx-classes | fn | public | `crates/fnx-classes/src/lib.rs:153` |
| neighbor_count_matches_neighbors_len | fnx-classes | fn | internal | `crates/fnx-classes/src/lib.rs:449` |
| neighbors | fnx-classes | fn | public | `crates/fnx-classes/src/lib.rs:139` |
| neighbors_iter | fnx-classes | fn | public | `crates/fnx-classes/src/lib.rs:146` |
| neighbors_iter_preserves_deterministic_order | fnx-classes | fn | internal | `crates/fnx-classes/src/lib.rs:435` |
| remove_edge | fnx-classes | fn | public | `crates/fnx-classes/src/lib.rs:337` |
| remove_node | fnx-classes | fn | public | `crates/fnx-classes/src/lib.rs:354` |
| remove_node_removes_incident_edges | fnx-classes | fn | internal | `crates/fnx-classes/src/lib.rs:481` |
| DependentUnblockMatrix | fnx-conformance | struct | public | `crates/fnx-conformance/src/lib.rs:110` |
| DependentUnblockRow | fnx-conformance | struct | public | `crates/fnx-conformance/src/lib.rs:102` |
