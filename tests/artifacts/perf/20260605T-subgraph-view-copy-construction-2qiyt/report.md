# br-r37-c1-2qiyt SubgraphView copy construction tax

## Target

Follow-up from `br-r37-c1-g114w`: exact `Graph`/`DiGraph`
`SubgraphView.copy()` had moved edge filtering out of the hot path, leaving
result graph construction as the next profile-backed cost.

Baseline cProfile on the pass-2 path:

- `_FilteredGraphView.copy`: 0.228 s
- `_FilteredGraphView._copy_induced_simple_fast`: 0.228 s
- `add_nodes_from`: 0.141 s

Baseline hyperfine:

- FrankenNetworkX: 627.1 ms
- NetworkX: 594.6 ms
- NetworkX gap: 1.05x on this noisy run

## Lever

One kept lever: when every selected node has empty node attributes, add the
node list directly instead of feeding `(node, attrs_dict)` tuples into
`add_nodes_from`.

This avoids the tuple-with-dict unhashable path and per-node attr merge work in
the common empty-node-attr case. Non-empty node attrs keep the old path.

Rejected during the same pass but not kept: a native PyO3 induced-copy builder.
It regressed the target harness because Python node-key conversion inside the
native method dominated the small-copy path.

## Proof

Golden source: NetworkX outputs from the pass-2 parity harness.

- Cases: 288 across `Graph`, `DiGraph`, `MultiGraph`, and `MultiDiGraph`
- Mismatches: 0
- Golden sha256: `d59bf72eb384ee5a2cfa0259051a1c6c5357b51dcd2e057d340b344cf1973d60`

Isomorphism:

- Ordering: unchanged; node order is still view iteration order, and edge order
  still follows parent neighbor/key order.
- Tie-breaking: unchanged; no algorithmic tie policy touched.
- Floating-point: N/A.
- RNG: N/A in runtime behavior; proof graph construction uses fixed seeds.
- Attr semantics: empty-node-attr copies still create result nodes with empty
  attr dicts; non-empty node attrs use the previous attr-copy path.

## Rebench

Same-environment hyperfine, 20 runs:

| Case | Mean | Delta |
| --- | ---: | ---: |
| fnx legacy node-attr path | 661.0 ms | baseline |
| fnx empty-node-attr shortcut | 607.5 ms | 1.09x faster |
| NetworkX | 554.5 ms | fnx gap 1.10x |

After cProfile:

- `_FilteredGraphView.copy`: 0.138 s
- `_FilteredGraphView._copy_induced_simple_fast`: 0.137 s
- `add_nodes_from`: 0.033 s

Score: Impact 1 x Confidence 4 / Effort 1 = 4.0, keep.

## Validation

- `rch exec -- python3 parity_proof.py`: passed, 288 cases / 0 mismatches.
- `rch exec -- python3 -m pytest tests/python/test_subgraph_node_order_divergence.py tests/python/test_subgraph_view_no_copy_perf.py tests/python/test_filtered_view_nodes_parity.py -q`: 66 passed.
- `rch exec -- python3 -m py_compile ...`: passed.
- `rch exec -- maturin develop --release --features pyo3/abi3-py310`: passed.
- `rch exec -- cargo check -p fnx-python --all-targets`: passed.
- `rch exec -- cargo clippy -p fnx-python --all-targets -- -D warnings`: passed.
- `rch exec -- cargo fmt -p fnx-python --check`: passed.
- `ubs` on the artifact harness: passed, no critical or warning issues.
- `ubs` on `python/franken_networkx/__init__.py`: timed out at 180 s in the
  known large-wrapper scanner path; no findings were emitted before timeout.

## Follow-up Primitive

The next target is not another native copy builder with per-node PyO3 key
conversion. The deeper primitive should avoid repeated empty-attr probing and
view construction work, likely by carrying graph-level empty-node-attr state or
a node-attr generation counter so exact induced copies can choose the cheap
node-list materialization path without per-node attr checks.
