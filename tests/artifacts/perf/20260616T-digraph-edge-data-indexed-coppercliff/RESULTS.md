# br-r37-c1-eqivz - DiGraph edges(data=True) indexed snapshot

## Decision

Rejected and source reverted. The indexed snapshot fast path preserved behavior, but it regressed the profile-backed native edge-data path and did not meet the measured win gate.

## Baseline

- Harness: `tests/artifacts/perf/20260615T-post-graph-attr-routing-boldfalcon/construction_attr_survey.py`
- Case: `digraph_attr`
- FNX survey median: `0.008591855003032833s`
- NetworkX survey median: `0.0065440149628557265s`
- FNX/NX median ratio: `1.3129332759476844x`
- Golden digest: `3f1de3be563f8e8f7a63710ca7bea1886888bd83417fcdade9249eee112d9d1c`
- cProfile `_native_edges_with_data`: `0.409s / 200 loops`
- Hyperfine FNX mean: `3.1660453026s`
- Hyperfine NetworkX mean: `2.2003787612000005s`

## Lever

When `succ_py_keys` is empty and all edge attr mirrors exist, build the `edges(data=True)` tuple cache through `cached_node_key_vec`, `edges_ordered_indices`, and ordered attr dict handles instead of the borrowed-edge path with per-edge key lookup.

The fast path was gated away from successor display overrides and missing attr mirrors, so fallback behavior remained the existing implementation.

## Isomorphism Proof

- Survey digest stayed `3f1de3be563f8e8f7a63710ca7bea1886888bd83417fcdade9249eee112d9d1c`.
- `tests/python/test_add_edges_attr_batch_parity.py -q`: `25 passed`.
- Live edge-data dict identity probe SHA: `49775e66a9b56a36161c8530879a13b04fe7bc108a3a69e236291ab4f98033fe`.
- Ordering: unchanged by construction because `edges_ordered_indices()` mirrors existing edge insertion order used by the no-data/data-key indexed caches.
- Tie-breaking: no graph algorithm tie-break path touched.
- Floating point: no arithmetic changed; edge weight values are passed through existing attr dictionaries.
- RNG: no RNG surface touched.

## After

- FNX survey median: `0.008759282005485147s`
- NetworkX survey median: `0.006598448031581938s`
- FNX/NX median ratio: `1.3274760918871953x`
- Golden digest: `3f1de3be563f8e8f7a63710ca7bea1886888bd83417fcdade9249eee112d9d1c`
- cProfile `_native_edges_with_data`: `0.447s / 200 loops`
- Hyperfine FNX mean: `3.2302701039399997s`
- Hyperfine NetworkX mean: `2.54807495964s`

## Score

Impact `0` x Confidence `5` / Effort `1` = `0.0`.

The source patch was reverted and a clean release-perf extension was reinstalled.
