# bfs_tree lazy edge metadata validation summary

Status: rejected candidate; no source code retained.

Commands:
- `rch exec -- .venv/bin/maturin develop --release --features pyo3/abi3-py310`
- `rch exec -- env PYTHONPATH=python .venv/bin/python tests/artifacts/perf/20260603T-bfs-tree-raw-construction/bench_bfs_tree_raw.py bench --n 8000 --m 4 --seed 42 --repeat 20 --engines fnx nx`
- `rch exec -- env PYTHONPATH=python .venv/bin/python tests/artifacts/perf/20260603T-bfs-tree-raw-construction/bench_bfs_tree_raw.py profile --n 8000 --m 4 --seed 42 --repeat 20 --output tests/artifacts/perf/20260603T-bfs-tree-lazy-edge-metadata/profile_baseline_fnx.txt --limit 80`
- `rch exec -- hyperfine --warmup 3 --runs 15 --export-json tests/artifacts/perf/20260603T-bfs-tree-lazy-edge-metadata/hyperfine_baseline.json 'env PYTHONPATH=python .venv/bin/python tests/artifacts/perf/20260603T-bfs-tree-raw-construction/bench_bfs_tree_raw.py bench --n 8000 --m 4 --seed 42 --repeat 3 --engines fnx >/dev/null'`
- `rch exec -- cargo check -p fnx-python --features pyo3/abi3-py310`
- `rch exec -- env PYTHONPATH=python .venv/bin/python -m pytest tests/python/test_attribute_access_parity.py::test_bfs_tree_returns_fnx_digraph tests/python/test_attribute_access_parity.py::test_bfs_tree_edge_attr_dicts_materialize_with_nx_semantics tests/python/test_traversal.py::TestBFS::test_bfs_tree tests/python/test_traversal.py::TestBFS::test_bfs_tree_reverse_on_digraph -q`
- `sha256sum -c tests/artifacts/perf/20260603T-bfs-tree-lazy-edge-metadata/artifact_sha256.txt`
- `ubs .beads/issues.jsonl tests/artifacts/perf/20260603T-bfs-tree-lazy-edge-metadata/alien_recommendation_card.md tests/artifacts/perf/20260603T-bfs-tree-lazy-edge-metadata/isomorphism_proof.md tests/artifacts/perf/20260603T-bfs-tree-lazy-edge-metadata/benchmark_report.md tests/artifacts/perf/20260603T-bfs-tree-lazy-edge-metadata/validation_summary.md`

Results:
- Behavior golden SHA stayed `40dd5c5bbd4df6a848c51d3980210cf060943460e9809e5a6d9a6bd9231916f2`.
- Focused pytest passed on the candidate.
- Direct FNX mean regressed `0.07658544930018252s -> 0.07933432019199245s`.
- Hyperfine regressed `0.7552698227200002s -> 0.7815417369066665s`.
- Restored source direct mean recorded as `0.07885979484854033s`.
- Artifact checksum verification passed; see `artifact_sha256_check.txt`.
- Pre-commit `ubs` on the scoped text/tracker files exited 0 and reported no recognizable source languages.

Next:
- Do not continue tuning BFS-tree edge metadata. The failed result indicates the remaining cost is deeper in native tree construction or a different active hotspot. Attack a different profile-backed primitive next.
