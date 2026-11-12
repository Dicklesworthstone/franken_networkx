# br-r37-c1-9hkgu pass 1: direct simple-Graph NodeDataView items

## Lever

Route only simple `Graph.nodes(data=True)` materialization through the original
PyO3 `NodeView.items` descriptor saved before the public Mapping-compatible
`items()` monkey patch. The public `NodeDataView` wrapper, `data=False`, attr
projection (`data="attr"`), DiGraph/MultiGraph paths, edge views, adjacency
views, graph storage, RNG, floating-point math, and traversal ordering are
unchanged.

## Profile-backed target

Baseline profile on the `watts_strogatz n=800` harness showed the target-specific
cost in `NodeDataView.__iter__ -> _materialize`:

- baseline cProfile: total exercise `0.921s`; `_materialize` cumulative `0.141s`
- candidate cProfile: total exercise `0.872s`; `_materialize` cumulative `0.115s`

The remaining dominant costs are harness normalization and JSON hashing, not this
dispatch layer.

## Benchmark

Same harness, same graph, same digest:

```text
baseline_loop_fnx_nodes_data mean   0.00044436343527761183 s/iter
candidate_loop_fnx_nodes_data mean  0.00035980414744699370 s/iter
self speedup                       1.2350147668686209x

baseline hyperfine FNX command      723.3482440600001 ms
candidate hyperfine FNX command     630.8217026000000 ms
command speedup                    1.146684137x
```

Score: Impact `3` x Confidence `4` / Effort `1` = `12.0`; keep threshold is `>= 2.0`.

## Isomorphism proof

The lever calls the same underlying simple-Graph node materializer already used
by the Rust `NodeView.items` method:

- Ordering: both old and new paths use the graph's existing node order.
- Tie-breaking: none; this is view materialization only.
- Floating point: none.
- RNG: none.
- Mutability/liveness: yielded attr dicts are the graph-owned `PyDict` objects;
  local identity smoke confirmed the old and new yielded dict objects are the
  same object for attr-present and attr-empty nodes.

Golden output is byte-identical:

```text
64875e70a976e5f4392b3037189280b32da02a3e7f205417132e2e09382eae99  baseline_golden.json
64875e70a976e5f4392b3037189280b32da02a3e7f205417132e2e09382eae99  candidate_golden.json
```

Target loop digest is unchanged:

```text
1b4d98e8952f4697588961e7ec8c64ff318f9bc220c37775a19daf409b7f3046  baseline/candidate nodes-data digest
```

## Validation

- `python -m py_compile python/franken_networkx/__init__.py tests/artifacts/perf/20260613T-9hkgu-view-materialization-boldfalcon/view_materialization_pass1.py` passed.
- `rch exec -- cargo check -p fnx-python --lib` passed on `vmi1227854`; pre-existing `fnx-generators` warnings were emitted by dependency checking.
- `rch exec -- pytest tests/python/test_nodes_data_view_liveness_parity.py tests/python/test_view_pickle_parity.py::test_node_data_view_pickle_roundtrips tests/python/test_view_pickle_parity.py::test_node_data_view_deepcopy_roundtrips -q` passed: `21 passed`.
- `git diff --check` passed.

Gate caveats:

- `rch exec -- cargo fmt --check` fails on pre-existing Rust formatting drift in
  untouched files (`crates/fnx-algorithms`, `crates/fnx-python/src/{algorithms,digraph,lib,readwrite}.rs`).
- `ubs python/franken_networkx/__init__.py tests/artifacts/perf/20260613T-9hkgu-view-materialization-boldfalcon/view_materialization_pass1.py` hung for over three minutes after `Scanning python...`; the exact stuck process tree for this run was terminated.

## Residual

The next deeper primitive is already represented by `br-r37-c1-4b5ie`: a kept-in-sync
Python node-attr dict mirror / view substrate for the remaining live-view gap.
