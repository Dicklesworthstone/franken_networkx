# Isomorphism Proof: PageRank absent-weight index COO

Bead: `br-r37-c1-04z53.17`

Baseline:
- fnx sample mean: 0.06574139425174508 s.
- nx sample mean: 0.015871380290870245 s.
- fnx and nx digest: `58d17b197d5e3e6d9055f9a1004c4962a177e1429f85e89b44dce73673491475`.
- hyperfine process mean: 2.3809479245399996 s.
- cProfile native adjacency cumulative time: 0.330 s across six public calls.

After:
- fnx sample mean: 0.06138227633103573 s.
- Sample speedup: 1.0710159052623032x.
- fnx digest: `58d17b197d5e3e6d9055f9a1004c4962a177e1429f85e89b44dce73673491475`.
- hyperfine process mean: 2.2784277788942857 s.
- Process speedup: 1.0449960040846529x.
- cProfile native adjacency-index cumulative time: 0.303 s across six public calls.

Behavior invariants:
- Ordering: `nodelist = list(G)` is unchanged and is still the only node order used to build the SciPy matrix and zip the final result.
- Tie-breaking: the SciPy CSR matrix coordinates still come from the graph's native adjacency traversal for the same `nodelist`; the PageRank power iteration and final `dict(zip(...))` path are unchanged.
- Floating point: the only new float data is `np.ones(len(rows), dtype=float)`, which is equivalent to the previous `default=1.0` unit-weight data for absent-weight PageRank; the SciPy normalization, matvec, convergence test, and `map(float, x)` path are unchanged.
- Weight behavior: this branch is active only when `pagerank_weight is None`; weighted calls and calls with present edge weight attributes continue through the existing weighted native/fallback routes.
- Multigraph behavior: unchanged because the native branch remains guarded by `not G.is_multigraph()`.
- RNG: none in the library path; the benchmark graph seed is fixed at 42.
- Golden output: baseline fnx, baseline nx, and after fnx SHA-256 digests are identical.

Rejected alternative:
- Raw native `_raw_pagerank` probe mean was 0.07623469695802972 s and digest was `a3b5053265f76b364252a7c3f1f6f2c6fad8e541d4ce6178bbfb4d0cefeb3c2f`.
- It was rejected because it regressed performance and did not preserve NetworkX-observable output.

Verification:
- `rch exec -- .venv/bin/python -m py_compile python/franken_networkx/__init__.py`: passed.
- `rch exec -- .venv/bin/python -m pytest tests/python/test_link_analysis_summarization_conformance.py tests/python/test_algorithm_family_conformance_harness.py -q -k 'pagerank'`: 28 passed, 114 deselected.
- `rch exec -- hyperfine ...`: before mean 2.3809479245399996 s, after mean 2.2784277788942857 s.
- `git diff --check -- python/franken_networkx/__init__.py .skill-loop-progress.md .beads/issues.jsonl tests/artifacts/perf/20260603T-pagerank-current`: passed.
- `timeout 180 ubs python/franken_networkx/__init__.py tests/artifacts/perf/20260603T-pagerank-current/alien_recommendation_card.md tests/artifacts/perf/20260603T-pagerank-current/isomorphism_proof.md tests/artifacts/perf/20260603T-pagerank-current/golden_sha256.txt`: timed out after preparing/scanning the specified files; no finding body was emitted before timeout.
