## Change: PageRank Absent-Weight Early Exit

- Ordering preserved: yes. The output still comes from `_pagerank_scipy`, which returns `dict(zip(nodelist, ...))`; `nodelist = list(G)` is unchanged.
- Tie-breaking unchanged: yes. PageRank has no discrete tie-break path in this wrapper.
- Floating-point: identical for the absent-attr case. NetworkX defines missing edge weights as unit weights, so `weight="missing"` with no matching attrs and `weight=None` construct the same transition matrix. Golden digest stayed `58d17b197d5e3e6d9055f9a1004c4962a177e1429f85e89b44dce73673491475`.
- RNG seeds: unchanged. Benchmark fixture uses `seed=42`; library path uses no RNG.
- Error behavior: attr-present, multigraph, helper-unavailable, non-string weight key, personalization, nstart, and dangling paths keep the existing behavior. Present string attrs still sync Python attrs before native weighted reads.
- Golden outputs: `baseline_pagerank_absent_old.jsonl`, `after_pagerank_absent_new.jsonl`, and `baseline_pagerank_absent_nx.jsonl` all have digest `58d17b197d5e3e6d9055f9a1004c4962a177e1429f85e89b44dce73673491475`.
- Current sampled-call benchmark: old fnx `0.022896937666 s` -> new fnx `0.019760648040 s` (`1.1587x`, `13.70%` faster); upstream nx `0.016487090084 s`.
- Current hyperfine process benchmark: old fnx `0.654571425963 s` -> new fnx `0.602487521537 s` (`1.0864x`, `7.96%` faster).
- Tests:
  - `rch exec -- .venv/bin/python -m pytest tests/python/test_pagerank_weight_parity.py tests/python/test_link_analysis_summarization_conformance.py -q`
  - `rch exec -- .venv/bin/python -m pytest tests/python/test_centrality_conformance_matrix.py tests/python/test_algorithm_family_conformance_harness.py tests/python/test_large_graph_value_parity.py -q -k pagerank`
