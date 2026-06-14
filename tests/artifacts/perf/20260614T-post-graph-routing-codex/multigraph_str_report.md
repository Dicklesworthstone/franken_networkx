# br-r37-c1-04z53.9100 MultiGraph String-Key Batch

## Change

Fresh exact integer-prefix `MultiGraph.add_edges_from([(int, int, str), ...])`
now validates in index space and bulk-loads the underlying `MultiGraph` rows via
`extend_fresh_int_prefix_keyed_edges_unrecorded`. Non-prefix, negative, bool,
tuple-input, non-string, empty-string, duplicate public-key, attributed, and
non-fresh shapes fall back to the existing NetworkX-compatible path.

## Baseline

- Golden bundle SHA: `e1eb93d52aa8b9b027d2e8233db864d9b64bb2bc24789d78d987821d7deb55c6`
- Direct FNX median: `0.23883166900486685s`
- Direct NetworkX median: `0.18448751099640504s`
- Hyperfine FNX mean: `3.19223369348s +/- 0.0702721041128108s`
- Hyperfine NetworkX mean: `2.42107715118s +/- 0.08053380001972422s`
- Profile: `_try_add_str_keyed_edges_from_batch` `1.546s` of `1.700s` for five 50k builds.

## Candidate

- Golden bundle SHA: `e1eb93d52aa8b9b027d2e8233db864d9b64bb2bc24789d78d987821d7deb55c6`
- Direct FNX median: `0.12084507499821484s` (`1.9763459041123104x`)
- Hyperfine FNX mean: `2.5860720628400005s +/- 0.09835807349971994s` (`1.2343947175139112x`)
- Candidate profile: `_try_add_str_keyed_edges_from_batch` `0.399s` of `0.479s` for five 50k builds.
- Score: `1.2343947175139112 impact x 4 confidence / 1 effort = 4.94`, keep.

## Isomorphism

- Ordering preserved: exact golden compares node order and `edges(keys=True, data=True)` order against NetworkX.
- Tie-breaking unchanged: duplicate public string keys fall back before mutation; repeated-pair key order remains sequential per pair.
- Display objects preserved: accepted node display objects are the first exact Python int objects from the input; string edge-key objects are mirrored as provided.
- Floating point: N/A.
- RNG: N/A.
- Golden verification: `sha256sum -c multigraph_str_sha256.txt` passed.

## Validation

- `rch exec -- cargo check -p fnx-python --lib` passed with pre-existing dead-code warnings.
- `rch exec -- cargo test -p fnx-classes multigraph_int_prefix_keyed_edges_match_string_batch --lib` passed.
- `rch exec -- cargo clippy -p fnx-classes --lib -- -D warnings` passed.
- `rch exec -- python3 -m pytest tests/python/test_ctor_str_and_third_element_parity.py tests/python/test_adj_row_key_parity.py -q` passed: `56 passed`.
- `ubs crates/fnx-classes/src/lib.rs crates/fnx-python/src/lib.rs` completed with exit 0, no critical findings.
- `rustfmt --edition 2024 --check crates/fnx-classes/src/lib.rs` passed.
- `rch exec -- cargo clippy -p fnx-python --lib -- -D warnings` is still blocked by pre-existing `cached_node_key_vec`, `NodeIteratorGuard::DiGraph`, collapsible-if, and needless-borrow warnings outside this lever.
