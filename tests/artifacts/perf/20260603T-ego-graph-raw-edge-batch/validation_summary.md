# ego_graph trusted raw edge batch validation summary

Status: kept candidate.

Commands:
- `rch exec -- .venv/bin/maturin develop --release --features pyo3/abi3-py310`
- `rch exec -- env PYTHONPATH=python .venv/bin/python tests/artifacts/perf/20260602T-traversal-residual-sweep/bench_traversal.py sample --impl fnx --op ego_graph_r2 --repeat 30 --n 3000 --m 4 --graph-seed 42`
- `rch exec -- env PYTHONPATH=python .venv/bin/python tests/artifacts/perf/20260602T-traversal-residual-sweep/bench_traversal.py sample --impl nx --op ego_graph_r2 --repeat 30 --n 3000 --m 4 --graph-seed 42`
- `rch exec -- env PYTHONPATH=python .venv/bin/python -m cProfile -s cumulative tests/artifacts/perf/20260602T-traversal-residual-sweep/bench_traversal.py sample --impl fnx --op ego_graph_r2 --repeat 20 --n 3000 --m 4 --graph-seed 42`
- `rch exec -- hyperfine --warmup 3 --runs 15 --export-json tests/artifacts/perf/20260603T-ego-graph-raw-edge-batch/hyperfine_baseline.json 'env PYTHONPATH=python .venv/bin/python tests/artifacts/perf/20260602T-traversal-residual-sweep/bench_traversal.py sample --impl fnx --op ego_graph_r2 --repeat 5 --n 3000 --m 4 --graph-seed 42 >/dev/null'`
- `RCH_ENV_ALLOWLIST=PYTHONPATH rch exec -- env PYTHONPATH=python .venv/bin/python -m py_compile python/franken_networkx/__init__.py`
- `RCH_ENV_ALLOWLIST=PYTHONPATH rch exec -- env PYTHONPATH=python .venv/bin/python -m pytest tests/python/test_ego_graph_node_order_parity.py tests/python/test_native_replacements_parity.py::TestEgoGraph::test_ego_graph_undirected_includes_predecessors tests/python/test_native_replacements_parity.py::TestEgoGraph::test_ego_graph_distance_parameter tests/python/test_quickwin_rewire_parity.py::test_ego_graph_matches_nx -q`
- `RCH_ENV_ALLOWLIST=CARGO_TARGET_DIR rch exec -- cargo check -p fnx-python --features pyo3/abi3-py310`
- `timeout 45 ubs python/franken_networkx/__init__.py tests/artifacts/perf/20260603T-ego-graph-raw-edge-batch/alien_recommendation_card.md tests/artifacts/perf/20260603T-ego-graph-raw-edge-batch/isomorphism_proof.md tests/artifacts/perf/20260603T-ego-graph-raw-edge-batch/benchmark_report.md tests/artifacts/perf/20260603T-ego-graph-raw-edge-batch/validation_summary.md`
- `ubs tests/artifacts/perf/20260603T-ego-graph-raw-edge-batch/alien_recommendation_card.md tests/artifacts/perf/20260603T-ego-graph-raw-edge-batch/isomorphism_proof.md tests/artifacts/perf/20260603T-ego-graph-raw-edge-batch/benchmark_report.md tests/artifacts/perf/20260603T-ego-graph-raw-edge-batch/validation_summary.md`
- `sha256sum -c tests/artifacts/perf/20260603T-ego-graph-raw-edge-batch/artifact_sha256.txt`

Results:
- Direct FNX mean improved `0.02699522003046392s -> 0.024855155232944525s`.
- Hyperfine mean improved `0.54359138932s -> 0.51429685616s`; confirm
  `0.5286960480266666s`.
- Golden SHA stayed
  `5dc8ab88ec0fd5490369d69f379aafc838d027576d99d986772bd178131888e3`.
- Focused ego parity passed: `13 passed`.
- `py_compile` passed.
- `cargo check -p fnx-python --features pyo3/abi3-py310` passed.
- Bounded `ubs` on the large generated Python wrapper timed out with exit
  `124` after entering Python scanning; see `ubs_changed_timeout45.log`.
- `ubs` on the scoped text artifacts exited `0` and reported no recognizable
  source languages.
- Artifact checksum verification passed; see `artifact_sha256_check.txt`.
