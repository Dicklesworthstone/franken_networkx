# br-r37-c1-85fvl benchmark report

## Target

- Kernel: `fnx.dag_longest_path(DiGraph)` native predecessor-DP fast path.
- Graph: deterministic 400-node DAG, 1600 edges, seed `8675309`.
- Profile-backed hotspot: after `br-r37-c1-pzutt`, cProfile still spends the public call's algorithm time inside `_dag_longest_path_digraph_native`.

## Lever

Replace the per-node predecessor candidate list:

```python
us = [(dist[u][0] + edge_weight, u) for u, edge_weight in pred_map[v]]
maxu = max(us, key=lambda x: x[0]) if us else (0, v)
```

with a streaming best-candidate scan. This removes the temporary `us` list and the `key` callback while preserving first-max tie-breaking.

## Baseline

- Direct rch 1000-sample mean for committed list body: `0.0013398678486410062s`.
- Amplified hyperfine over 1000 inner samples: `7.48110754465s +/- 0.07275816858s`.
- Digest: `1da1199afe41ba00e0c57975dbb5bd5cdef6529b59a0acea38956812d860aa44`.

## After

- Direct rch 1000-sample mean for streaming loop: `0.0012417738991498482s`.
- Amplified hyperfine over 1000 inner samples: `7.34577720590s +/- 0.03531650210s`.
- Digest: `1da1199afe41ba00e0c57975dbb5bd5cdef6529b59a0acea38956812d860aa44`.

## Delta

- Direct mean: `0.0013398678486410062s -> 0.0012417738991498482s`, 7.32% faster, 1.079x.
- Hyperfine: `7.48110754465s -> 7.34577720590s`, 1.81% faster, 1.018x.
- Behavior: exact path and digest unchanged.

## Score gate

- Impact: 2
- Confidence: 4
- Effort: 1
- Score: `2 * 4 / 1 = 8.0`

Decision: keep and commit.
