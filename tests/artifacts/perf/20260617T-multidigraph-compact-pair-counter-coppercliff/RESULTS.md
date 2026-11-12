# MultiDiGraph compact pair counter rejection

Bead: `br-r37-c1-04z53.9138`

Target: fresh exact-int attributed `MultiDiGraph.add_edges_from` construction in
`crates/fnx-python/src/digraph.rs`.

Lever tried: replace `HashMap<(usize, usize), usize>` directed pair counters with
a compact `u64` encoded pair key when both endpoint insertion indexes fit in 32
bits.

Outcome: rejected and source reverted.

Behavior proof:

- Directed multigraph construction digest remained
  `58267b72563bb3af74585c8d9d4e4dc2e46cbb5f253675efdebda5ea12604b24`.
- Focused parity test passed:
  `test_multidigraph_fresh_exact_int_attr_batch_matches_nx_order_keys_and_copies`.
- Full attr-batch parity file passed: `27 passed`.
- The lever does not touch ordering policy outside directed pair auto-key
  bookkeeping, floating-point paths, or RNG paths.

Performance evidence:

- Survey FNX median regressed from `0.020272175956051797s` to
  `0.022121180954854935s`.
- Survey FNX mean regressed from `0.02356276858721257s` to
  `0.02636431259281166s`.
- Focused profile total regressed from `9.139s` to `9.652s`.
- `_multidigraph_attr` regressed from `3.500s` to `3.686s`.
- `_multi_add_edges_from` regressed from `3.031s` to `3.182s`.
- `_try_add_attr_edges_from_batch` regressed from `2.930s` to `3.075s`.
- Hyperfine FNX loop50 mean regressed from `2.54724497166s` to
  `2.65940463394s`.

Validation commands run before rejection:

- `cargo fmt --check`
- `cargo check -p fnx-python --all-targets`
- `maturin develop --release --features pyo3/abi3-py310`
- `.venv/bin/python -m pytest tests/python/test_add_edges_attr_batch_parity.py::test_multidigraph_fresh_exact_int_attr_batch_matches_nx_order_keys_and_copies -q`
- `.venv/bin/python -m pytest tests/python/test_add_edges_attr_batch_parity.py -q`

Conclusion: the compact directed key worsens the actual construction profile on
this benchmark. The source was reverted; only this artifact records the failed
probe.
