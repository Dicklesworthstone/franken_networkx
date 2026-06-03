# Alien Recommendation Card: PageRank absent-weight index COO

Bead: `br-r37-c1-04z53.17`

Profile target:
- `tests/artifacts/perf/20260603T-pagerank-current/profile_fnx.txt`
- `pagerank_absent_weight` on GNP(1000, p=0.05, seed=42), repeats=24.
- Baseline fnx mean: 0.06574139425174508 s.
- Baseline NetworkX mean: 0.015871380290870245 s.
- Baseline fnx / NetworkX ratio: 4.1421346503531105.
- Baseline cProfile repeat-5 showed six public calls spent 0.330 s in native `_fnx.adjacency_arrays`.

Primitive harvested:
- Alien graveyard constants-kill-you discipline: avoid manufacturing a full float data vector in native Rust when all edge weights are known to be unit weights.
- Narrow drop-in replacement: keep the same SciPy PageRank solver and same node order, but populate COO from compact native row/column indices plus `np.ones`.

Rejected probe:
- Raw native `_raw_pagerank` mean: 0.07623469695802972 s.
- Raw native digest: `a3b5053265f76b364252a7c3f1f6f2c6fad8e541d4ce6178bbfb4d0cefeb3c2f`.
- Verdict: rejected because it was slower than baseline and did not preserve the golden digest.

One lever:
- In `_pagerank_scipy`, when `pagerank_weight is None` for a simple graph, use native `adjacency_index_arrays` to get row/column indices and allocate unit float data in NumPy before constructing the same SciPy CSR matrix.

Score:
- Impact 2: focused sampled-call mean improved from 0.06574139425174508 s to 0.06138227633103573 s, and hyperfine process mean improved from 2.3809479245399996 s to 2.2784277788942857 s.
- Confidence 3: golden digest stayed identical and targeted PageRank tests passed.
- Effort 1: one narrow Python wrapper branch plus proof artifacts.
- Opportunity score: 2 * 3 / 1 = 6.0. Keep.
