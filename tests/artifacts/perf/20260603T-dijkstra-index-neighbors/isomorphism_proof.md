# Isomorphism Proof: Dijkstra Integer Neighbor Indices

Bead: `br-r37-c1-fwudd`

## Change

The undirected `multi_source_dijkstra` relaxation loop now iterates `Graph::neighbors_indices(u_idx)` and resolves node names through `ordered_nodes[v_idx]` instead of iterating `neighbors_iter(ordered_nodes[u_idx])` and performing `get_node_index(v_name)` for every directed edge scan.

## Profile Target

The bead supplied the profile target:

- Workload: `single_source_dijkstra_path_length(BA(2000, 4, seed=42), source=0, weight="weight")`.
- Gap: fnx 41 ms vs NetworkX 4.7 ms, 8.7x slower.
- cProfile per call: `_fnx.single_source_dijkstra` 21 ms, `_fnx_sync_attrs_to_inner` 11.6 ms, `graph_edge_weights_all_int` 2.6 ms, `check_dijkstra_edge_weights_fast` 2.1 ms.
- Hot lever: remove the string-keyed adjacency lookup and per-edge `get_node_index` lookup in the Rust kernel.

## Baseline / After

RCH Criterion command:

```bash
RCH_ENV_ALLOWLIST=CARGO_TARGET_DIR rch exec -- cargo bench -p fnx-algorithms --bench algorithm_benchmarks single_source_dijkstra -- --sample-size 10 --warm-up-time 1 --measurement-time 3
```

Criterion mean estimates:

- `grid/400`: 2.6011 ms -> 2.3699 ms, 8.89% faster.
- `grid/2025`: 32.681 ms -> 28.003 ms, 14.32% faster.
- `grid/4096`: 89.843 ms -> 82.857 ms, 7.77% faster.

Score: Impact 3 x Confidence 4 / Effort 1 = 12.0.

## Behavior Invariants

- Ordering preserved: yes. `adj_indices` is maintained in the same insertion order as the string adjacency used by `neighbors_iter`, and `ordered_nodes` is captured once before the loop exactly as before.
- Tie-breaking unchanged: yes. The relaxation sequence is unchanged, so `seq_counter`, heap push order, stale-entry handling, finalization order, predecessor replacement order, and emitted distance/path dict order remain identical.
- Floating point unchanged: yes. The same `edge_weight_or_default` call happens in the same edge visitation order, so the `d + edge_weight` operation order is unchanged.
- RNG unchanged: yes. The library path uses no RNG; benchmark graph construction is deterministic.
- Directed graphs unchanged: yes. This lever only changes the undirected `Graph` implementation of `multi_source_dijkstra`; directed Dijkstra still uses the existing successor string iteration path.

## Golden Output

The Python golden check compares raw `_fnx.single_source_dijkstra_path_length` output from the pre-lever string-neighbor loop against the optimized integer-neighbor loop on `BA(2000, 4, seed=42)` with deterministic positive weights. The SHA payload preserves dict insertion order and full `.17g` distance formatting.

Golden digest:

- Baseline old loop: `67f8231e2189a5c974539d90362b582e3403f630f5b6c073a3df6caa012f8e05`
- Optimized loop: `67f8231e2189a5c974539d90362b582e3403f630f5b6c073a3df6caa012f8e05`

Verification command:

```bash
sha256sum -c tests/artifacts/perf/20260603T-dijkstra-index-neighbors/golden_sha256.txt
```
