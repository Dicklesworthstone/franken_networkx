# br-r37-c1-04z53.9117 - DiGraph edges row-stream iterator

## Target

- Workload: `list(DiGraph.edges())`
- Graph: `DiGraph(gnp_random_graph(n=1800, p=0.006, seed=14, directed=True))`
- Edge count: 19,448
- Profile-backed hotspot before change:
  - `_DiGraphEdgeView.__iter__` / `_materialize`: 0.313s cumulative over 200 loops
  - `_native_edges_no_data`: 0.227s cumulative over 200 loops
- Lever: replace the bare no-data DiGraph edge view path with a native guarded row-stream iterator so iteration walks successor rows directly instead of first materializing a Python edge list.

## Behavior Proof

- Golden output SHA-256 before: `fd0f49af3820608d93affd3c407c68a96df1bf3c01d765dfa0e2f05e45cd53f4`
- Golden output SHA-256 after: `fd0f49af3820608d93affd3c407c68a96df1bf3c01d765dfa0e2f05e45cd53f4`
- Exact ordered edge list matched NetworkX before and after.
- Mutation parity matched NetworkX for edge and node mutation during iteration:
  - Exception type: `RuntimeError`
  - Message: `dictionary changed size during iteration`
- Ordering proof: iterator preserves NetworkX node-major successor insertion order by walking internal node indices in insertion order and each successor row in stored insertion order.
- Tie-breaking proof: no algorithmic tie-breaking surface; this is a view iteration path only.
- Floating-point proof: no floating-point operations.
- RNG proof: graph construction uses the same fixed NetworkX seed only in the harness; the implementation does not consume RNG.

## Benchmarks

All benchmark commands ran through `rch exec -- hyperfine` or the harness outputs captured in this directory.

- Baseline direct FNX target timer, 200 loops: 1.2076488739694469s total, 0.006038244369847234s/loop
- After direct FNX target timer, 200 loops: 1.037713079014793s total, 0.005188565395073965s/loop
- Direct target improvement: 1.16x

- Baseline hyperfine, 200 loops: 1.63218915086s +/- 0.02774144150s
- After hyperfine, 200 loops: 1.60150892838s +/- 0.04246057366s
- 200-loop command improvement: 1.02x

- Parent-commit baseline hyperfine, 1000 loops: 6.391149485034286s +/- 0.1653098191141476s
- Candidate hyperfine, 1000 loops: 5.738730834177143s +/- 0.09864555940230786s
- 1000-loop target-shaped command improvement: 1.11x

## Score

- Impact: 2
- Confidence: 5
- Effort: 2
- Score: 5.0

## Validation

- `PYTHONPATH=python python3 -m py_compile python/franken_networkx/__init__.py tests/artifacts/perf/20260615T-digraph-edges-stream-coppercliff/digraph_edges_stream_harness.py`
- `PYTHONPATH=python python3 -m pytest tests/python/test_view_str_parity.py tests/python/test_to_edgelist_view_type.py tests/python/test_graph_utilities.py -k 'edge or DiGraph or edgelist' -q`
  - Result: 366 passed, 265 deselected
- `cargo fmt --package fnx-python --check`
- `rch exec -- cargo check -p fnx-python --lib --features pyo3/abi3-py310`
- `rch exec -- cargo clippy -p fnx-python --lib --features pyo3/abi3-py310 -- -D warnings`
- `git diff --check`
- `timeout 240s ubs --only=rust,python --skip-python=20 --files=crates/fnx-python/src/digraph.rs,python/franken_networkx/__init__.py,tests/artifacts/perf/20260615T-digraph-edges-stream-coppercliff/digraph_edges_stream_harness.py .`
  - Result: timed out in Python phase after Rust scan completed with no findings emitted.
