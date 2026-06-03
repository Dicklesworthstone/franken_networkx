# Weighted Sparse Direct Python Attr Read Rejection

- Bead: `br-r37-c1-04z53.16`
- Candidate lever: make native `adjacency_arrays` read weighted values directly from Python-visible `edge_py_attrs` and remove the wrapper pre-sync.
- Result: rejected; no code change kept.

## Baseline

- Fresh sweep fnx mean: `0.03835297760087997` s
- Fresh sweep NetworkX mean: `0.027018616397981532` s
- Fresh sweep ratio: `1.4195019106805626`
- Stronger sampled-call mean: `0.046443076999518475` s
- Stronger sampled-call median: `0.039414810002199374` s
- Hyperfine process mean: `0.7920765822685716` s
- Hyperfine process median: `0.7877681498400001` s
- Golden digest: `67df0f0442003e5ba6963b28f9aa88837492b8a9953d9e62550cc3c88ece6a77`
- cProfile repeat-5: `adjacency_matrix` / `to_scipy_sparse_array` at `0.309` s with native `adjacency_arrays` at `0.146` s, `_sync_rust_edge_attrs` at `0.013` s, and NumPy `asarray` at `0.018` s.

## Candidate After

- Sampled-call mean: `0.1886426860013065` s
- Sampled-call median: `0.1791504509965307` s
- Hyperfine process mean: `1.845877955602857` s
- Hyperfine process median: `1.84317741846` s
- Golden digest: `67df0f0442003e5ba6963b28f9aa88837492b8a9953d9e62550cc3c88ece6a77`
- cProfile repeat-5: native `adjacency_arrays` regressed to `0.856` s.

## Decision

The candidate preserved output bytes but moved the hot native work to per-edge Python-dict lookups. The cost was far larger than the removed sync.

- Impact: 1
- Confidence: 1
- Effort: 2
- Score: `Impact 1 x Confidence 1 / Effort 2 = 0.5`

Because the score is below the `2.0` keep threshold, the Rust/Python/test edits were manually removed. The extension was rebuilt after removal so subsequent profiling uses the kept implementation.
