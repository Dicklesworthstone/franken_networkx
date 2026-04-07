# E2E Scenario Matrix + Oracle Contract (V1)

- generated_at_utc: 2026-04-07T16:38:48.707728+00:00
- baseline_comparator: legacy_networkx/main@python3.12
- journey_count: 12
- fixture_inventory_count: 84
- covered_fixture_count: 84
- uncovered_fixture_count: 0

## Journey Coverage

| Journey | Packet | Strict Fixture | Hardened Fixture | Hardened Strategy |
|---|---|---|---|---|
| `J-GRAPH-CORE` | `FNX-P2C-001` | `graph_core_shortest_path_strict.json` | `graph_core_mutation_hardened.json` | `native_fixture` |
| `J-VIEWS` | `FNX-P2C-002` | `generated/view_neighbors_strict.json` | `generated/view_neighbors_strict.json` | `mode_override_fixture` |
| `J-DISPATCH` | `FNX-P2C-003` | `generated/dispatch_route_strict.json` | `generated/dispatch_route_strict.json` | `mode_override_fixture` |
| `J-CONVERT` | `FNX-P2C-004` | `generated/convert_edge_list_strict.json` | `generated/convert_edge_list_strict.json` | `mode_override_fixture` |
| `J-SHORTEST-PATH-COMPONENTS` | `FNX-P2C-005` | `generated/components_connected_strict.json` | `generated/flow_max_missing_capacity_hardened.json` | `mode_override_fixture` |
| `J-STRUCTURE` | `FNX-P2C-005` | `generated/structure_articulation_points_strict.json` | `generated/structure_articulation_points_strict.json` | `mode_override_fixture` |
| `J-CENTRALITY` | `FNX-P2C-005` | `generated/centrality_edge_betweenness_strict.json` | `generated/centrality_degree_selfloop_hardened.json` | `mode_override_fixture` |
| `J-MATCHING` | `FNX-P2C-005` | `generated/matching_maximal_strict.json` | `generated/matching_maximal_isolated_hardened.json` | `mode_override_fixture` |
| `J-READWRITE` | `FNX-P2C-006` | `generated/readwrite_roundtrip_strict.json` | `generated/readwrite_hardened_malformed.json` | `native_fixture` |
| `J-GENERATORS` | `FNX-P2C-007` | `generated/generators_path_strict.json` | `generated/generators_cycle_strict.json` | `mode_override_fixture` |
| `J-RUNTIME-OPTIONAL` | `FNX-P2C-008` | `generated/runtime_config_optional_strict.json` | `generated/runtime_config_optional_strict.json` | `mode_override_fixture` |
| `J-CONFORMANCE-HARNESS` | `FNX-P2C-009` | `generated/conformance_harness_strict.json` | `generated/conformance_harness_strict.json` | `mode_override_fixture` |

## Replay Metadata Contract

| Schema Ref |
|---|
| `artifacts/conformance/schema/v1/structured_test_log_schema_v1.json` |
| `artifacts/conformance/schema/v1/e2e_step_trace_schema_v1.json` |
| `artifacts/conformance/schema/v1/forensics_bundle_index_schema_v1.json` |

## Failure Class Taxonomy

| Failure Class | Source | Description |
|---|---|---|
| `fixture_io` | `fnx-conformance fixture loading` | Fixture file cannot be read from deterministic fixture inventory. |
| `fixture_schema` | `fnx-conformance fixture parsing` | Fixture payload is malformed or violates expected operation schema. |
| `graph_mutation` | `Graph operation execution` | Graph mutation output diverges from expected nodes/edges/attrs parity. |
| `algorithm` | `fnx-algorithms parity checks` | Algorithm output (e.g., shortest path) diverges from oracle expectation. |
| `algorithm_centrality` | `fnx-algorithms centrality checks` | Centrality score/ordering output diverges from oracle expectation. |
| `algorithm_components` | `fnx-algorithms components checks` | Component partition/count output diverges from oracle expectation. |
| `algorithm_structure` | `fnx-algorithms structure checks` | Structural graph outputs (articulation points/bridges) diverge from oracle expectation. |
| `dispatch` | `fnx-dispatch parity checks` | Dispatch route/action does not match deterministic policy expectation. |
| `convert` | `fnx-convert parity checks` | Conversion pipeline output diverges from expected normalized graph state. |
| `readwrite` | `fnx-readwrite parity checks` | Read/write parser or serializer output diverges from oracle expectations. |
| `views` | `fnx-views parity checks` | Graph view query output diverges from deterministic ordering expectations. |
| `generators` | `fnx-generators parity checks` | Generator-produced graph structure/order diverges from oracle fixtures. |
| `algorithm_matching` | `fnx-algorithms matching checks` | Matching algorithm output diverges from oracle expectation. |
| `algorithm_flow` | `fnx-algorithms flow checks` | Flow/connectivity algorithm output diverges from oracle expectation. |
| `algorithm_distance` | `fnx-algorithms distance checks` | Distance measure output (eccentricity/diameter/radius/center/periphery) diverges from oracle expectation. |
| `algorithm_mst` | `fnx-algorithms MST checks` | Minimum spanning tree output (edges/total_weight) diverges from oracle expectation. |
| `algorithm_coloring` | `fnx-algorithms coloring checks` | Graph coloring output diverges from oracle expectation. |
| `algorithm_connectivity` | `fnx-algorithms connectivity checks` | Node connectivity or minimum node cut output diverges from oracle expectation. |
| `algorithm_euler` | `fnx-algorithms euler checks` | Euler path/circuit algorithm output diverges from oracle expectation. |
