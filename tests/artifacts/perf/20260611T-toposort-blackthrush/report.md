# br-r37-c1-04z53.62 topological_sort native-generation flatten

## Target

Post-db0qr residual profile selected `topological_sort_dag450`.

- Profile artifact: `tests/artifacts/perf/20260611T-post-db0qr-residual-blackthrush/top_profile.txt`
- Profile site: `python/franken_networkx/__init__.py:13970(topological_sort)`
- One lever: exact `DiGraph` flattens native `topological_generations` instead of replaying Kahn in Python.

## Proof

Harness: `tests/artifacts/perf/20260611T-toposort-blackthrush/harness_toposort.py`

- Ordered topological outputs match NetworkX exactly across empty, single, chain, diamond, wide FIFO, disconnected insertion-order, string-node, multigraph, and dag450 fixtures.
- Cycle and undirected error type/message parity preserved.
- Mutation fingerprint preserved against the pre-change FNX baseline.
- Floating-point surface: none.
- RNG surface: none.
- Parity golden sha256: `fb7bc80f1dd7cefccd0c2e12dde1c72f7c31f550451ea57cc99dad6ae006b267`
- Mutation golden sha256: `12fe5f9e7f21910db7af0ade4812c3598373f44d0e4f170c5a3a4af481ddb39b`

## Bench

Direct harness, dag450:

| Metric | Before | After | Delta |
| --- | ---: | ---: | ---: |
| FNX best sec/call | 0.000319045 | 0.000224070 | 1.42x faster |
| FNX median sec/call | 0.000338761 | 0.000230522 | 1.47x faster |
| FNX/NetworkX best ratio after | n/a | 0.727 | FNX faster |
| FNX/NetworkX median ratio after | n/a | 0.719 | FNX faster |

Hyperfine process harness:

| Metric | Before | After | Delta |
| --- | ---: | ---: | ---: |
| Mean wall sec | 1.129760 | 0.805105 | 1.40x faster |
| Min wall sec | 0.877005 | 0.772485 | 1.14x faster |

Score: Impact 2 * Confidence 4 / Effort 1 = 8.0.

## Validation

- `python -m py_compile python/franken_networkx/__init__.py tests/artifacts/perf/20260611T-toposort-blackthrush/harness_toposort.py`
- `python tests/artifacts/perf/20260611T-toposort-blackthrush/harness_toposort.py --phase after --expect-parity-sha ... --expect-mutation-sha ...`
- `rch exec -- hyperfine ... baseline_hyperfine.json`
- `rch exec -- hyperfine ... after_hyperfine.json`
- `pytest tests/python/test_traversal.py tests/python/test_dag_topology_conformance.py tests/python/test_dag_topology_metamorphic.py tests/python/test_topological_generations_parity.py tests/python/test_more_directed_only_message_parity.py tests/python/test_error_messages.py -k 'topological_sort or topological_generations or dag or topology' -q`
  - Result: 111 passed, 83 deselected.
- `git diff --check`
- `rch exec -- cargo check -p fnx-python --all-targets --features pyo3/abi3-py310`
  - Result: passed; existing `fnx-generators` warnings observed.

Known unrelated gate state:

- `cargo fmt --check --package fnx-python` reports pre-existing Rust formatting drift in `crates/fnx-python/src/*.rs`.
- `cargo clippy -p fnx-python --all-targets --features pyo3/abi3-py310 -- -D warnings` fails on a pre-existing `clippy::needless_range_loop` in `crates/fnx-classes/src/digraph.rs:1413`.
- `ubs python/franken_networkx/__init__.py tests/artifacts/perf/20260611T-toposort-blackthrush/harness_toposort.py` was attempted and terminated after several minutes without completing on the large Python module.
