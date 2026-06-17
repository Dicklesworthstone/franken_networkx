# br-r37-c1-04z53.9136: reject MultiGraph borrowed view-order edge path

## Target

The post-keyed-data routing profile showed `multigraph_attr` still behind
NetworkX and spending material time in first-call edge view materialization:

- Survey ratio: `1.2417825082841973` on the fresh local baseline.
- FNX median: `0.01893132203258574s`; NetworkX median: `0.015245279995724559s`.
- Focused profile total: `9.978s` over 160 construction/digest loops.
- `_native_edge_view_list`: `1.596s`.

The candidate added an inner borrowed view-order edge traversal for MultiGraph
and routed the PyO3 `edges(keys=True, data=True)` materialization path through
it when all live edge-attribute mirrors already existed.

## Decision

Rejected. Source and focused test changes were reverted.

The intended view hotspot improved, but the total and hyperfine gates did not:

- `_native_edge_view_list`: `1.596s -> 1.370s`.
- `_digest_graph`: `6.408s -> 6.068s`.
- Total profile: `9.978s -> 9.714s`.
- `_try_add_attr_edges_from_batch`: `2.811s -> 2.884s`.
- `multigraph_attr` survey FNX median: `0.01893132203258574s -> 0.019600016996264458s`.
- Hyperfine FNX mean: `2.6671670343200007s -> 2.71550976848s`.
- Hyperfine FNX median: `2.7069374023200004s -> 2.71933149808s`.

The lever is below the `2.0` keep threshold because the user-facing looped
benchmark regressed and the survey median regressed despite the local view
materialization win.

## Behavior Proof

- Digest parity stayed true for `multigraph_attr`.
- Golden digest stayed unchanged:
  `50644c550f48ebc209b8fa5bb649acf1961385c2b71d65f0a572cb3e2a22ae99`.
- Focused candidate validation before rejection:
  `cargo check -p fnx-python --all-targets`,
  `cargo test -p fnx-classes multigraph_edges_view_ordered_preserves_traversed_endpoint_orientation`,
  `maturin develop --release --features pyo3/abi3-py310`,
  `pytest tests/python/test_add_edges_attr_batch_parity.py::test_multigraph_keyed_data_view_preserves_orientation_and_live_attrs -q`,
  `pytest tests/python/test_add_edges_attr_batch_parity.py -q`.
- The construction/view path has no floating-point or RNG ordering beyond the
  already checked weighted-degree parity in the focused test.

## Follow-Up Routing

Do not repeat the borrowed edge-view traversal family for this profile. The
next MultiGraph attempt should target the construction path directly or remove
a Python-level digest traversal altogether with a larger structural primitive.
