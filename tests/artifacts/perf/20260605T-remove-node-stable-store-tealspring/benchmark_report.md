# br-r37-c1-xh7jk Benchmark Report

## Target

- Bead: `br-r37-c1-xh7jk`
- Surface: exact Python `Graph.remove_nodes_from`
- Profile-backed hotspot: public `remove_nodes_from(range(...))` rebuilt Rust graph indexes once per removed node. Baseline cProfile showed the native binding at `0.130s` for one `n=1000, m=8000` removal batch.
- Primitive: batch tombstone/compaction. Collect present removal nodes once, retain survivor nodes/adjacency/edges in storage order, and rebuild node/edge indexes once.

## Baseline

Commands were run through `rch exec` after a release `maturin develop --features pyo3/abi3-py310` build.

- Golden command: `./.venv/bin/python remove_node_batch_bench.py golden --nodes 300 --edges 1600`
- Golden SHA: `357f32eeb2db2d1b6441a251503b5efc8af2cebc121234caeb7b60dbfa7580e2`
- cProfile: `baseline_cprofile.txt`
  - `Graph.remove_nodes_from`: `0.130s`
- Hyperfine: `baseline_hyperfine.json`
  - FNX mean: `1.619494870735s +/- 0.079118475700s`
  - NetworkX mean: `0.382664115860s +/- 0.016458450829s`
  - Baseline process gap: FNX was `4.23x` slower than NetworkX.

## After

Commands were run through `rch exec` after the one-lever change and release extension rebuild.

- Golden command: `./.venv/bin/python remove_node_batch_bench.py golden --nodes 300 --edges 1600`
- Golden SHA: `357f32eeb2db2d1b6441a251503b5efc8af2cebc121234caeb7b60dbfa7580e2`
- cProfile: `after_cprofile.txt`
  - `Graph.remove_nodes_from`: `0.004s`
- Hyperfine: `after_hyperfine.json`
  - FNX mean: `0.543478902345s +/- 0.056199949171s`
  - NetworkX mean: `0.384518099845s +/- 0.028167270410s`
  - After process gap: FNX is `1.41x` slower than NetworkX.
- Direct timed section after rebuild:
  - FNX mean: `0.005390836409s`, digest `ef9cdaf4ea778286cb601d98557fa93c7e2e28c14da637043fac6cd7daf4f77f`
  - NetworkX mean: `0.001241957495s`, digest `ef9cdaf4ea778286cb601d98557fa93c7e2e28c14da637043fac6cd7daf4f77f`

## Delta

- Hyperfine FNX process envelope: `1.619494870735s -> 0.543478902345s`, `2.98x` faster.
- Native binding profile: `0.130s -> 0.004s`, `32.5x` faster.
- Semantic golden SHA unchanged.
- Score: Impact `4` x Confidence `5` / Effort `2` = `10.0`; PRODUCTIVE, keep.

## Validation

- `cargo fmt -p fnx-classes -p fnx-python --check`: passed.
- `rch exec -- cargo test -p fnx-classes remove_nodes_from_matches_repeated_removal_and_rebuilds_indices`: passed.
- `rch exec -- cargo check -p fnx-classes --all-targets`: passed.
- `rch exec -- cargo check -p fnx-python --features pyo3/abi3-py310 --all-targets`: passed.
- `rch exec -- cargo clippy -p fnx-classes --all-targets -- -D warnings`: passed.
- `rch exec -- cargo clippy -p fnx-python --features pyo3/abi3-py310 --all-targets --no-deps -- -D warnings`: passed.
- `rch exec -- ./.venv/bin/python -m pytest tests/python/test_attribute_access_parity.py::TestRemoveBunchMaterialized::test_remove_nodes_from_generator_reading_self tests/python/test_attribute_access_parity.py::TestRemoveBunchMaterialized::test_remove_nodes_from_materialized_matches_nx_after_batch_compaction -q`: `2 passed`.
- `git diff --check` on touched paths: passed.
- `sha256sum -c artifact_sha256.txt`: passed.
- UBS touched-file scan: exited `1` on pre-existing broad-file heuristics. The only critical entry is an existing test assert at `tests/python/test_attribute_access_parity.py:159`; the new remove-node test hunk is not flagged. The artifact harness only received informational `Any` typing notes.

## Reprofile Note

After the lever, cProfile is dominated by deterministic graph construction (`build_graph` and `add_edges_from`). The next deeper primitive for this bead family should target shared construction/mutation substrate rather than another per-node removal loop.
