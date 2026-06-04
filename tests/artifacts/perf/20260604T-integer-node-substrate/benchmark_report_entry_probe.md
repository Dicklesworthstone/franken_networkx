# br-r37-c1-04z53.49: MultiGraph fresh-edge single entry probe

## Target

- Profile-backed bead: `[perf] Integer-node substrate for construction hot paths`.
- Baseline hotspot: `multigraph_int_keys` construction still spent `1.526s` of profiled time in native `_fast_add_explicit_int_edge` over 450000 calls.
- Alien-graveyard primitive: §7.7 Swiss Tables / probe-path profiling. The shipped lever reduces the existing hash-map probe path without changing the map implementation.

## Lever

`MultiGraph::add_fresh_edge_unrecorded` previously checked `self.edges.get(&edge_key)` and then immediately looked up the same key again through `self.edges.entry(edge_key)`. The kept change uses one `IndexMap::entry` probe and handles occupied/vacant buckets in that entry state.

The preliminary integer canonical cache lever was rejected and removed: direct loop improved, but hyperfine regressed from `1.240s` to `1.347s`, below the keep bar.

## Benchmarks

Baseline and after commands used the same `rch exec` benchmark harness and the release Python extension built via `maturin develop --release --features pyo3/abi3-py310`.

| Case | Baseline | After | Delta |
| --- | ---: | ---: | ---: |
| `multigraph_int_keys` direct FNX mean | `0.2690699283s` | `0.2223946222s` | `1.21x` |
| `multigraph_int_keys` direct FNX median | `0.2687584730s` | `0.2215527230s` | `1.21x` |
| `multigraph_int_keys` hyperfine mean | `1.2398131408s` | `1.1851016608s` | `1.05x` |
| `multigraph_int_keys` cProfile total | `2.947s` | `2.521s` | `1.17x` |
| `_fast_add_explicit_int_edge` cProfile | `1.526s` | `1.351s` | `1.13x` |
| `multigraph_str_keys` direct FNX mean | `0.2718651859s` | `0.2276283733s` | `1.19x` |

Score: `(Impact 5.0 * Confidence 0.9) / Effort 2.0 = 2.25`, keep.

## Behavior Proof

- Ordering: vacant `IndexMap::entry` insertion uses the same `EdgeKey::new(left, right)` canonical key, inserts key `0`, and then updates adjacency in the same left/right order as before. Occupied non-empty buckets still return `None`, so Python fallback/tie-breaking behavior is unchanged.
- Tie-breaking: explicit edge-key identity is still recorded in `fnx-python` after the storage call returns `Some(0)`. Existing-edge buckets still do not overwrite stored keys or attrs in the fast path.
- Floating point: no FP arithmetic or comparison was introduced. Hash-equal Python key cases stay on the existing Python/generic fallback when the pair already exists.
- RNG: no RNG state is read or written.
- Golden output SHA256:
  - `multigraph_int_keys`: `6041eefb1e549a77af5c18a4e08ab1dc24e9df42e2e9ef094e810d35bedf58dc` before, after, and NetworkX oracle.
  - `multigraph_str_keys`: `a316d777cf3e4070855b2fca932a4f8f993dee8bbacf6d430f95624dd04d41bf` before, after, and NetworkX oracle.
  - Duplicate explicit-key oracle: 3 cases matched NetworkX return tokens and digest; log SHA256 `71d93c87225497e0aedc1e2192832ad7154583114feb01b0a0313fc8791974d4`.

## Verification

- `cargo fmt -p fnx-classes --check`: passed.
- `rch exec -- cargo check -p fnx-python --features pyo3/abi3-py310 --all-targets`: passed.
- `rch exec -- cargo clippy -p fnx-classes --all-targets -- -D warnings`: passed.
- `rch exec -- cargo test -p fnx-classes multigraph_add_fresh_edge_unrecorded_rejects_occupied_bucket -- --nocapture`: 1 passed.
- `pytest tests/python/test_attribute_access_parity.py tests/python/test_to_undirected_parity.py -q`: 163 passed.
- `ubs crates/fnx-classes/src/lib.rs`: exit 0; no critical issues, fmt/clippy/build health clean, broad file-level warning inventory unchanged.

Next shifted bottleneck: `_fast_add_explicit_int_edge` still dominates at `1.351s`; the next primitive should move from string-keyed fresh-edge insertion toward an integer-slot edge construction path with order-preserving Python object side tables.
