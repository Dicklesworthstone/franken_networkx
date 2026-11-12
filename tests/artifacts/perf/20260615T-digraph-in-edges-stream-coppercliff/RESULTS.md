# br-r37-c1-04z53.9118 - DiGraph in_edges indexed materialization

## Target

- Workload: `list(DiGraph.in_edges())`
- Graph: `DiGraph(gnp_random_graph(n=1800, p=0.006, seed=15, directed=True))`
- Edge count: 19,579
- Profile-backed hotspot before change:
  - `_DiEdgeMethodView.__iter__` / `_digraph_in_edges`: 0.412s cumulative over 200 loops
  - `_native_in_edges_no_data`: 0.315s cumulative over 200 loops
- Kept lever: for the common `pred_py_keys.is_empty()` path, materialize in-edges by node indices and one cached node-key vector instead of repeated `nodes_ordered()` string traversal and `py_pred_key` recovery. The final source uses checked `get()` lookups with explicit internal-invariant `RuntimeError`s instead of unchecked indexing.

## Rejected Lever

- Native row-stream iterator was tested first.
- RCH hyperfine, 200-loop command: 1.643s baseline to 1.582s stream candidate, only 1.04x.
- Direct timer: 1.087237053s baseline to 1.079290290s stream candidate, effectively flat.
- Reason rejected: Rust already materialized this list efficiently enough that per-item Python iteration cost dominated the stream route.

## Behavior Proof

- Golden output SHA-256 before: `b2b8e19419757a9b417df5aeaa1f646f759726f9a4aebc2d573e417193357c61`
- Golden output SHA-256 after checked indexed lever: `b2b8e19419757a9b417df5aeaa1f646f759726f9a4aebc2d573e417193357c61`
- Exact ordered `in_edges()` list matched NetworkX before and after.
- Ordering proof: the indexed branch preserves NetworkX target-node-major order, then predecessor insertion order, by walking target node indices in insertion order and each stored predecessor row in order.
- Tie-breaking proof: no algorithmic tie-breaking surface; this is a view materialization path only.
- Floating-point proof: no floating-point operations.
- RNG proof: graph construction uses the same fixed NetworkX seed only in the harness; the implementation does not consume RNG.
- Mutation behavior: unchanged from baseline. The harness exposes a pre-existing NetworkX parity gap where FNX materialized `InEdgeView` iteration does not raise on node/edge mutation during iteration. This commit does not alter that behavior; a guarded iterator route should be handled as a separate correctness/perf lever.

## Benchmarks

All hyperfine commands ran through `rch exec -- hyperfine`.

- Baseline direct FNX target timer, 200 loops: 1.0872370530269109s total, 0.0054361852651345546s/loop
- After checked indexed direct FNX target timer, 200 loops: 0.8875921809813008s total, 0.004437960904906504s/loop
- Direct target improvement: 1.22x

- Baseline cProfile total, 200 loops: 0.469s
- After checked indexed cProfile total, 200 loops: 0.304s
- Profile improvement: 1.54x

- Baseline `_native_in_edges_no_data`, 200 loops: 0.315s
- After checked indexed `_native_in_edges_no_data`, 200 loops: 0.155s
- Native hotspot improvement: 2.03x

- Baseline hyperfine, 200-loop command: 1.643s +/- 0.049s
- After checked indexed hyperfine, 200-loop command: 1.54962675372s +/- 0.17230263642s
- 200-loop command improvement: 1.06x

- Parent-commit baseline hyperfine, 1000-loop command: 6.370596491222857s +/- 0.4534111871785368s
- Checked candidate hyperfine, 1000-loop command: 5.143146165222857s +/- 0.11979232346413549s
- 1000-loop target-shaped command improvement: 1.24x

## Score

- Impact: 2
- Confidence: 5
- Effort: 2
- Score: 5.0

## Validation

- `PYTHONPATH=python python3 -m py_compile tests/artifacts/perf/20260615T-digraph-in-edges-stream-coppercliff/digraph_in_edges_stream_harness.py`
- `PYTHONPATH=python python3 -m pytest tests/python/test_view_str_parity.py tests/python/test_to_edgelist_view_type.py tests/python/test_graph_utilities.py -k 'in_edges or edge or DiGraph or edgelist' -q`
  - Result: 366 passed, 265 deselected
- `cargo fmt --package fnx-python --check`
- `rch exec -- cargo check -p fnx-python --lib --features pyo3/abi3-py310`
- `rch exec -- cargo clippy -p fnx-python --lib --features pyo3/abi3-py310 -- -D warnings`
- `git diff --check`
- `timeout 240s ubs --only=rust,python --skip-python=20 --files=crates/fnx-python/src/digraph.rs,tests/artifacts/perf/20260615T-digraph-in-edges-stream-coppercliff/digraph_in_edges_stream_harness.py .`
  - Result: exit 0; no critical findings. UBS emitted broad warning inventory for existing `digraph.rs` patterns and noted benchmark-harness subprocess calls without explicit timeouts.
