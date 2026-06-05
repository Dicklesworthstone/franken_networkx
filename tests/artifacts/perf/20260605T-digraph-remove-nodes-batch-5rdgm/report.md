# br-r37-c1-5rdgm Benchmark Report

## Target

- Bead: `br-r37-c1-5rdgm`
- Surface: Python `DiGraph.remove_nodes_from`
- Profile-backed hotspot: prior `DiGraph.remove_node x500` artifacts showed the
  Rust substrate fixed to O(degree), leaving the Python public batch path paying
  per-victim PyO3 canonicalization, attr cleanup, and `IndexMap::shift_remove`
  node-row compaction.
- One lever: collect present canonical victims once, retain survivors in the
  Rust `DiGraph` storage once, prune Python node/edge attrs and directed row-key
  overrides by the same victim set.

## Baseline

Baseline was captured through `rch exec` before the change and then re-captured
from a detached f485 worktree for the sparse target shape after the harness was
refined.

- Golden command: `python digraph_remove_nodes_batch_bench.py golden --nodes 300 --edges 1600`
- Golden SHA: `536bb003276301015c74aa917da27bbb466a798b18b775b761a4a6a766bf34e1`
- Broad process hyperfine, n=2000/e=16000/loops=20:
  - FNX: `4.111213931700s +/- 0.313751664457s`
  - NetworkX: `1.421992566100s +/- 0.272880108380s`
- Sparse target hyperfine from f485, n=5000/e=5000/loops=3:
  - FNX: `0.810822467460s +/- 0.051743678131s`
  - NetworkX: `0.364668583460s +/- 0.020638215089s`
- Sparse target direct timed removal section:
  - FNX mean: `0.087376869322s`
  - Digest: `4818dcc69e640d7feb05c03f12887564b0f77e237910b1d4cdfd613eaffdbefd`

## After

After values were captured through `rch exec` after a release `maturin develop
--features pyo3/abi3-py310` rebuild of the optimized extension.

- Golden command: `python digraph_remove_nodes_batch_bench.py golden --nodes 300 --edges 1600`
- Golden SHA: `536bb003276301015c74aa917da27bbb466a798b18b775b761a4a6a766bf34e1`
- Broad process hyperfine, n=2000/e=16000/loops=20:
  - FNX: `3.926568391580s +/- 0.251758969087s`
  - NetworkX: `1.310809354580s +/- 0.073076240123s`
- Sparse target hyperfine, n=5000/e=5000/loops=3:
  - FNX: `0.626847683630s +/- 0.077959994616s`
  - NetworkX: `0.545985086130s +/- 0.057437541807s`
- Sparse target direct timed removal section:
  - FNX mean: `0.013400568336s`
  - Digest: `4818dcc69e640d7feb05c03f12887564b0f77e237910b1d4cdfd613eaffdbefd`

## Delta

- Sparse target hyperfine FNX process: `0.810822467460s -> 0.626847683630s`,
  `1.29x` faster.
- Sparse target direct removal section: `0.087376869322s -> 0.013400568336s`,
  `6.52x` faster.
- Broad construction-dominated hyperfine still improves slightly:
  `4.111213931700s -> 3.926568391580s`, `1.05x` faster.
- Semantic golden SHA unchanged.
- Score: Impact `3` x Confidence `5` / Effort `2` = `7.5`; PRODUCTIVE, keep.

## Validation

- `cargo fmt -p fnx-classes -p fnx-python --check`: passed.
- `rch exec -- cargo check -p fnx-classes --all-targets`: passed.
- `rch exec -- cargo check -p fnx-python --features pyo3/abi3-py310 --all-targets`: passed.
- `rch exec -- cargo clippy -p fnx-classes --all-targets -- -D warnings`: passed.
- `rch exec -- cargo clippy -p fnx-python --features pyo3/abi3-py310 --all-targets --no-deps -- -D warnings`: passed.
- `rch exec -- cargo test -p fnx-classes remove_node -- --nocapture`: passed.
- `rch exec -- python -m pytest tests/python/test_attribute_access_parity.py::TestRemoveBunchMaterialized::test_remove_nodes_from_generator_reading_self tests/python/test_attribute_access_parity.py::TestRemoveBunchMaterialized::test_remove_nodes_from_materialized_matches_nx_after_batch_compaction -q`: `2 passed`.
- `git diff --check` on touched paths: passed.
- `ubs` on touched paths: passed, exit 0.

## Reprofile Note

After the batch compaction, the broader process profile is dominated by graph
construction and `DiGraph.add_edges_from`. The next deeper primitive should target
directed construction/mutation ingestion, especially cache-friendly edge ingest
and row-key handling, rather than another `remove_nodes_from` loop tweak.
