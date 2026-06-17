# br-r37-c1-qk88a: reject MultiDiGraph unique-pair key0 construction

## Target

`multidigraph_attr` construction after the keyed data view keep still spent most
of its construction time in `MultiDiGraph._try_add_attr_edges_from_batch`.
The candidate replaced per-edge auto-key pair counts with a duplicate detector
for batches whose directed pairs are unique, assigning key `0` directly and
falling back before mutation when any parallel pair appears.

## Decision

Rejected. Source changes were reverted.

The benchmark median improved, but the profile-backed hotspot regressed:

- Total cProfile time: `9.506s -> 9.930s` over 160 construction/digest loops.
- `_multidigraph_attr`: `3.601s -> 3.729s`.
- `_multi_add_edges_from`: `3.107s -> 3.207s`.
- `_try_add_attr_edges_from_batch`: `3.006s -> 3.102s`.
- Edge-data view digest path `__call__`: `0.965s -> 0.994s`.

The local hyperfine loop still moved in the right direction:

- FNX mean: `2.58155574168s -> 2.45938273136s`.
- FNX median: `2.58092075668s -> 2.47010899016s`.

That improvement is not enough to keep the lever because the profile gate says
the exact construction target got slower. Score is below the `2.0` keep
threshold.

## Behavior Proof

- Digest parity stayed true for `multidigraph_attr`.
- Golden digest stayed unchanged:
  `58267b72563bb3af74585c8d9d4e4dc2e46cbb5f253675efdebda5ea12604b24`.
- The candidate preserved edge order, first-seen node order, auto-key display
  for unique pairs, copied source attr dictionaries, and live edge attr dict
  behavior in focused tests before rejection.
- No floating-point or RNG behavior is in this construction path.

## Validation Run Before Rejection

- `cargo fmt --check`
- `cargo check -p fnx-python --all-targets`
- `cargo clippy -p fnx-python --all-targets -- -D warnings`
- `maturin develop --release --features pyo3/abi3-py310`
- `pytest tests/python/test_add_edges_attr_batch_parity.py::test_multidigraph_fresh_exact_int_attr_batch_matches_nx_order_keys_and_copies tests/python/test_add_edges_attr_batch_parity.py::test_multidigraph_keyed_data_view_preserves_live_attrs_for_mirrored_and_plain_edges -q`
- `pytest tests/python/test_add_edges_attr_batch_parity.py -q`

## Follow-Up Routing

Do not repeat the key assignment micro-lever family for this profile. The next
profile-backed attack should target a structurally different cost center, such
as graph digest/materialization passes or a construction path that can remove a
Python-level traversal rather than only changing the Rust auto-key bookkeeping.
