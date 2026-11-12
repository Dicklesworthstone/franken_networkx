# br-r37-c1-85fvl isomorphism proof

## Change

The fast path now scans `pred_map[v]` once and updates the best predecessor only when `candidate_len > best_len`.

## Proof obligations

- Ordering preserved: yes. `topological_sort(G)` output and `_native_in_edges_data_key` target/source order are unchanged.
- Tie-breaking unchanged: yes. The old `max(us, key=lambda x: x[0])` returned the first maximum. The new loop updates only on strict `>`, so equal-length candidates keep the first predecessor.
- Floating-point: unchanged operation order per candidate until comparison; each candidate computes `dist[u][0] + edge_weight` once in predecessor order. No reduction sum is reordered.
- RNG seeds: unchanged. The benchmark DAG uses seed `8675309`; production code uses no RNG.
- Golden output: path and digest remain `1da1199afe41ba00e0c57975dbb5bd5cdef6529b59a0acea38956812d860aa44`.

## Fallback

Revert the commit to restore the list-comprehension body.
