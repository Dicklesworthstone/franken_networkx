# Default Sparse Native Index NumPy Handoff Rejection

- Bead: `br-r37-c1-04z53.15`
- Candidate lever: pre-materialize default native COO `rows` and `cols` as `np.intp` arrays before `scipy.sparse.coo_array`.
- Result: rejected; no code change kept.

## Baseline

- Fresh sweep fnx mean: `0.04833716540015302` s
- Fresh sweep NetworkX mean: `0.02691468739649281` s
- Fresh sweep ratio: `1.7959400638051521`
- Stronger sampled-call mean: `0.039125229084068756` s
- Stronger sampled-call median: `0.030117026493826415` s
- Hyperfine process mean: `0.6558863026942857` s
- Hyperfine process median: `0.65908179698` s
- Golden digest: `987fb0c41578a61146699304815a73d3c6d70160384e8fb3046d1d0c7b7d13c6`
- cProfile repeat-5: `adjacency_matrix` / `to_scipy_sparse_array` at `0.263` s with native `adjacency_index_arrays` at `0.123` s, SciPy COO at `0.020` s, and NumPy conversion at `0.011` s.

## Candidate After

- Sampled-call mean: `0.03845895350120069` s
- Sampled-call median: `0.03203077599755488` s
- Hyperfine process mean: `0.6470090224771428` s
- Hyperfine process median: `0.65111903362` s
- Golden digest: `987fb0c41578a61146699304815a73d3c6d70160384e8fb3046d1d0c7b7d13c6`
- cProfile repeat-5: `adjacency_matrix` / `to_scipy_sparse_array` worsened to `0.295` s, with native `adjacency_index_arrays` at `0.151` s and explicit NumPy `asarray` at `0.014` s.

## Decision

The candidate preserved the golden digest and improved process-level hyperfine by a small amount, but the hot sampled median regressed from `0.030117026493826415` s to `0.03203077599755488` s and the post-profile moved the wrong direction. That is not a profile-confirmed real win.

- Impact: 1
- Confidence: 1
- Effort: 1
- Score: `Impact 1 x Confidence 1 / Effort 1 = 1.0`

Because the score is below the `2.0` keep threshold, the code edit was manually removed and no optimization change was kept.

## Validation While Evaluating

- `rch exec -- .venv/bin/python -m py_compile python/franken_networkx/__init__.py tests/python/test_to_scipy_sparse_default_native_parity.py`: passed.
- `rch exec -- .venv/bin/python -m pytest tests/python/test_to_scipy_sparse_default_native_parity.py tests/python/test_io_conversion_parity.py -q -k 'scipy_sparse or to_scipy_sparse'`: 7 passed, 12 deselected.
- `rch exec -- cargo check -p fnx-python --all-targets`: passed.
- `ubs tests/python/test_to_scipy_sparse_default_native_parity.py`: exit 0; informational Bandit assert notes in tests only.
