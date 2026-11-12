# Criterion Results: Dijkstra Integer Neighbor Indices

Bead: `br-r37-c1-fwudd`

Command, both runs:

```bash
RCH_ENV_ALLOWLIST=CARGO_TARGET_DIR rch exec -- cargo bench -p fnx-algorithms --bench algorithm_benchmarks single_source_dijkstra -- --sample-size 10 --warm-up-time 1 --measurement-time 3
```

Baseline: `multi_source_dijkstra` used `neighbors_iter(ordered_nodes[u_idx])` and `get_node_index(v_name)` in the hot relaxation loop.

After: `multi_source_dijkstra` uses `neighbors_indices(u_idx)` and resolves names from `ordered_nodes[v_idx]`.

| Case | Baseline mean estimate | After mean estimate | Delta |
| --- | ---: | ---: | ---: |
| `single_source_dijkstra/grid/400` | 2.6011 ms | 2.3699 ms | 8.89% faster |
| `single_source_dijkstra/grid/2025` | 32.681 ms | 28.003 ms | 14.32% faster |
| `single_source_dijkstra/grid/4096` | 89.843 ms | 82.857 ms | 7.77% faster |

Score:

- Impact: 3
- Confidence: 4
- Effort: 1
- Score: `3 * 4 / 1 = 12.0`

Verdict: keep.
