# DOC-PASS-05 Complexity, Performance, and Memory Characterization (V1)

- generated_at_utc: 2026-02-17T03:22:39.066393+00:00
- baseline_comparator: legacy_networkx/main@python3.12
- operation_families: 6
- operations: 20
- high_risk_operations: 13
- hotspot_hypotheses: 8

## Family Overview

| Family | Operations | High Risk Ops |
|---|---:|---:|
| `graph_storage_semantics` | 4 | 2 |
| `algorithmic_core` | 4 | 3 |
| `generator_workloads` | 3 | 1 |
| `conversion_and_io` | 5 | 4 |
| `dispatch_runtime_policy` | 2 | 1 |
| `conformance_execution` | 2 | 2 |

## Operation Matrix

| Operation | Time | Space | Risk |
|---|---|---|---|
| `graph_add_node_with_attrs` | O(1) amortized | O(1) incremental | medium |
| `graph_add_edge_with_attrs` | O(1) amortized | O(1) incremental | high |
| `graph_remove_node` | O(deg(v)) | O(1) additional | high |
| `graph_neighbors_projection` | O(deg(v)) | O(deg(v)) output-bound | medium |
| `algo_shortest_path_unweighted` | O(V + E) | O(V) | high |
| `algo_connected_components` | O(V + E) | O(V) | high |
| `algo_degree_centrality` | O(V + E) | O(V) | medium |
| `algo_closeness_centrality` | O(V * (V + E)) | O(V) | high |
| `gen_cycle_graph` | O(V) | O(V) | medium |
| `gen_complete_graph` | O(V^2) | O(V^2) | medium |
| `gen_gnp_random_graph` | O(V^2) expected | O(V + E) | high |
| `convert_from_edge_list` | O(V + E) | O(V + E) | high |
| `convert_from_adjacency` | O(V + E) | O(V + E) | high |
| `rw_read_edgelist` | O(L) where L is input lines | O(V + E) | high |
| `rw_write_json_graph` | O(V + E) | O(V + E) serialization buffer | medium |
| `rw_read_json_graph` | O(V + E) | O(V + E) | high |
| `dispatch_backend_resolve` | O(B * F) where B=backends and F=feature checks | O(B) | high |
| `runtime_decision_theoretic_action` | O(1) | O(1) | medium |
| `conformance_run_smoke` | O(F * (V + E)) where F is fixture count | O(F + mismatch_count) | high |
| `conformance_run_fixture` | O(op_count * (V + E)) per fixture | O(mismatch_count + witness_count) | high |

## Hotspot Hypotheses

- `HS-001` (algo_shortest_path_unweighted): BFS frontier allocation churn dominates p95 latency on medium-density graphs.
  - test_plan: Profile queue growth + allocator samples on fixed graph density buckets.
  - expected_signal: queue push/pop hotspots exceed 30% of inclusive CPU time.
- `HS-002` (algo_connected_components): Visited-set hash pressure is the dominant memory tail contributor for large sparse graphs.
  - test_plan: Track allocations and resident memory while sweeping node cardinality with fixed degree.
  - expected_signal: visited-state allocations account for majority of retained bytes at p99.
- `HS-003` (algo_closeness_centrality): Repeated all-source traversals dominate runtime; batch-level caching may reduce wall-clock without parity drift.
  - test_plan: Compare baseline against one-lever cache memoization with deterministic keying.
  - expected_signal: single-lever memoization lowers p95 latency while preserving exact output ordering.
- `HS-004` (rw_read_edgelist): Line tokenization and malformed-row handling dominate parser CPU under adversarial input mix.
  - test_plan: Replay malformed-heavy corpora and sample parser branch hit rates.
  - expected_signal: malformed-row branches exceed nominal parse path in adversarial fixtures.
- `HS-005` (convert_from_adjacency): High fan-out adjacency payloads create allocation spikes in edge materialization.
  - test_plan: Run adjacency fan-out sweeps and compare allocation histograms.
  - expected_signal: allocation peaks scale superlinearly with fan-out unless pre-sized buffers are used.
- `HS-006` (gen_gnp_random_graph): Random graph generation becomes quadratic bottleneck at higher node counts.
  - test_plan: Sweep n/p grids with fixed seed to isolate candidate loop costs.
  - expected_signal: edge sampling loop dominates total runtime above target density threshold.
- `HS-007` (dispatch_backend_resolve): Backend capability filtering is negligible at current scale but can become visible with expanded registry breadth.
  - test_plan: Synthetic backend fan-out benchmark with deterministic feature vectors.
  - expected_signal: resolve latency scales linearly with backend count and feature cardinality.
- `HS-008` (conformance_run_fixture): Structured-log emission and mismatch serialization dominate harness runtime for larger fixture bundles.
  - test_plan: Measure fixture replay with/without structured log compression while preserving schema fidelity.
  - expected_signal: log serialization and mismatch formatting consume majority of post-execution wall-clock.

## Optimization Risk Note Policy

- Every operation is linked to at least one explicit parity risk note.
- One-lever optimization policy is mandatory and enforced by validation.
- Replay commands for all operation families are rch-offloaded.
