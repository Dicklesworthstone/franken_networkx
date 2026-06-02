## Change: `is_connected` Integer-Adjacency Bitmap BFS

- Ordering preserved: yes. `is_connected` returns only a bool publicly; Rust witness fields keep the same algorithm name and complexity claim.
- Tie-breaking unchanged: yes. Connectivity has no observable tie-break output, and traversal order is not exposed.
- Floating point: none.
- RNG seeds: unchanged. Benchmark fixture uses BA(5000, 4, seed=42); library path uses no RNG.
- Error behavior: Python wrapper still rejects null graphs and directed graphs before entering the Rust kernel.
- Golden output: `baseline_is_connected.jsonl` and `after_is_connected.jsonl` both have digest `3cbc87c7681f34db4617feaa2c8801931bc5e42d8d0f560e756dd4cd92885f18`.
- Sampled-call benchmark: old fnx `0.001861601718 s` -> new fnx `0.000117984752 s` (`15.7783x`, `93.66%` faster); after-run nx `0.001621428312 s`.
- Reprofile: native `_fnx.is_connected` cumulative time over 96 calls dropped from 0.740 s to 0.011 s.
- Tests:
  - `rch exec -- cargo test -p fnx-algorithms test_is_connected_uses_indexed_traversal_semantics -- --nocapture`
  - `rch exec -- cargo check -p fnx-algorithms --all-targets`
  - `rch exec -- cargo clippy -p fnx-algorithms --all-targets -- -D warnings`
  - `rch exec -- .venv/bin/python -m pytest tests/python/test_connectivity.py tests/python/test_connectivity_cross_type.py tests/python/test_connectivity_metamorphic_invariants.py -q`
