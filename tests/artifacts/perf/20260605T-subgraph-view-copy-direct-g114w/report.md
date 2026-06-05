# br-r37-c1-g114w SubgraphView direct copy materialization

## Target

After `br-r37-c1-rezuw`, `SubgraphView.copy()` on a 50-node induced subgraph
of a 2000-node / 8000-extra-edge parent graph shifted from visible-node scans
to per-edge filtered adjacency wrapper materialization.

## Baseline Profile

Baseline cProfile, same harness:

- `_time_copy`: 0.556 s
- `_FilteredGraphView.copy`: 0.486 s
- `_FilteredGraphView._edges`: 0.401 s
- `_FilteredNeighborMap.__iter__`: 0.234 s
- `_FilteredGraphView._node_visible`: 65,697 calls / 0.105 s

## Lever

One implementation lever: for exact `Graph` / `DiGraph` induced subgraph views
with the default edge filter, copy directly from the parent graph's raw neighbor
iterator and `get_edge_data()`.

Fallbacks are unchanged for multigraphs, subclasses, nested filtered views, and
custom edge filters.

## Proof

Golden source: NetworkX outputs from `parity_proof.py`.

- Cases: 288 across `Graph`, `DiGraph`, `MultiGraph`, and `MultiDiGraph`.
- Mismatches: 0.
- Golden sha256: `d59bf72eb384ee5a2cfa0259051a1c6c5357b51dcd2e057d340b344cf1973d60`.

Isomorphism:

- Ordering: preserved against NetworkX for sparse set-order and dense
  parent-order regimes.
- Tie-breaking: unchanged; edge order follows parent neighbor/key order.
- Floating-point: N/A.
- RNG: N/A in runtime behavior; proof graph construction uses fixed seeds.
- Custom edge filters: still use the old filtered-edge path and remain covered.

## Rebench

Rebuilt extension with `rch exec -- maturin develop --release --features
pyo3/abi3-py310`, then ran same-environment hyperfine:

| Case | Mean | Delta |
| --- | ---: | ---: |
| fnx old path (`--disable-direct-fnx`) | 535.7 ms | baseline |
| fnx direct path | 383.7 ms | 1.40x faster |
| NetworkX | 342.6 ms | fnx gap narrowed to 1.12x |

The original pre-edit pass-2 hyperfine baseline was `fnx 495.8 ms` vs
`NetworkX 381.3 ms` (NetworkX 1.30x faster). The final direct path is below
that fnx baseline and close to the rebuilt NetworkX comparator.

After cProfile:

- `_time_copy`: 0.140 s
- `_FilteredGraphView.copy`: 0.082 s
- `_FilteredGraphView._copy_induced_simple_fast`: 0.082 s
- `_FilteredGraphView._edges`: removed from the hot path

Score: Impact 3 x Confidence 5 / Effort 2 = 7.5, keep.

## Validation

- `rch exec -- python3 parity_proof.py`: passed, 288 cases / 0 mismatches.
- `rch exec -- python3 -m pytest tests/python/test_subgraph_node_order_divergence.py tests/python/test_subgraph_view_no_copy_perf.py tests/python/test_filtered_view_nodes_parity.py -q`: 66 passed.
- `rch exec -- python3 -m py_compile ...`: passed.
- `rch exec -- maturin develop --release --features pyo3/abi3-py310`: passed.
- `rch exec -- cargo check -p fnx-python --all-targets`: passed.
- `rch exec -- cargo clippy -p fnx-python --all-targets -- -D warnings`: passed.
- `rch exec -- cargo fmt -p fnx-python --check`: passed.
- `ubs` on non-wrapper touched files: passed, no critical or warning issues.
- `ubs` including `python/franken_networkx/__init__.py`: timed out at 180 s
  in the known large-wrapper scanner path; no findings were emitted before
  timeout.

## Reprofile Follow-up

The remaining cost is result graph node/edge insertion and import/setup noise
on this harness. The next deeper primitive should target construction-tax
materialization for small graph copies, not another filtered-view wrapper loop.
