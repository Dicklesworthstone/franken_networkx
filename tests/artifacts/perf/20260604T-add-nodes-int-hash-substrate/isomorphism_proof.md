# Isomorphism Proof

Change: `Graph.add_nodes_from(range(stop))` uses an implicit consecutive-int
display-key range instead of storing every Python int object in `node_key_map`.

## Ordering

Preserved. The inner graph still receives canonical node strings in ascending
range order via `extend_nodes_unrecorded`, so `nodes_ordered()` and every view
built from it keeps the original insertion order. Copy/subgraph conversion paths
now iterate `inner.nodes_ordered()` and materialize display keys through
`py_node_key`, preserving the same visible order for implicit keys.

## Tie-breaking

Unchanged. There is no algorithmic tie-break in node construction. The only
first-object rule is Python dict node-key display identity. Existing explicit
keys in `node_key_map` still win. For implicit range keys, re-adding hash-equal
float/bool aliases does not overwrite the synthesized int display key; removing
a node and adding it again makes the later object the new first key, matching
NetworkX.

## Floating-point

N/A. The optimized path performs no floating-point arithmetic.

## RNG

N/A. The optimized path has no random behavior.

## Golden Outputs

`after_golden.json` compares FrankenNetworkX against NetworkX for range order,
node data, first-object preservation, remove/re-add behavior, copy, shallow
copy, subgraph, and pickle round trips. It reports `match=true`.

`sha256sum -c after_golden.sha256` passed:

`1447bf5307da29fd7e718cc3121349ecc0ba0325f31b7aa9584ff98b5639d446`

The construction benchmark digest also stayed unchanged:

`eae2ed4eadc93d3264aef2fb5cd05bce54b2c934b5805383f8e5ad4113505b75`

## Validation

- `rch exec -- cargo fmt -p fnx-python --check`
- `rch exec -- cargo check -p fnx-python --features pyo3/abi3-py310 --all-targets`
- `rch exec -- cargo clippy -p fnx-python --features pyo3/abi3-py310 --all-targets -- -D warnings`
- `rch exec -- maturin develop --release --features pyo3/abi3-py310`
- `rch exec -- python3 -m pytest tests/python/test_node_key_canonicalization_parity.py tests/python/test_nodes_data_view_liveness_parity.py tests/python/test_view_pickle_parity.py tests/python/test_subgraph_node_order_divergence.py -q`
- `ubs crates/fnx-python/src/lib.rs tests/python/test_node_key_canonicalization_parity.py`
