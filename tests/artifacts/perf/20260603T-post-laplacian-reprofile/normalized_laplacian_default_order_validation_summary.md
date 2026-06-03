# br-r37-c1-u1de5 Validation Summary

## Benchmarks

- `RCH_ENV_ALLOWLIST=PYTHONPATH rch exec -- env PYTHONPATH=python .venv/bin/python tests/artifacts/perf/20260602T-vs-upstream-sweep/bench_vs_upstream.py sweep --n 8000 --m 4 --repeats 10`
- `RCH_ENV_ALLOWLIST=PYTHONPATH rch exec -- env PYTHONPATH=python .venv/bin/python tests/artifacts/perf/20260602T-vs-upstream-sweep/bench_vs_upstream.py bench --case normalized_laplacian_default --impl fnx --n 8000 --m 4 --repeats 12`
- `RCH_ENV_ALLOWLIST=PYTHONPATH rch exec -- env PYTHONPATH=python .venv/bin/python tests/artifacts/perf/20260602T-vs-upstream-sweep/bench_vs_upstream.py bench --case normalized_laplacian_default --impl nx --n 8000 --m 4 --repeats 12`
- `RCH_ENV_ALLOWLIST=PYTHONPATH rch exec -- env PYTHONPATH=python .venv/bin/python tests/artifacts/perf/20260602T-vs-upstream-sweep/bench_vs_upstream.py profile --case normalized_laplacian_default --impl fnx --n 8000 --m 4 --repeats 8 --limit 50 --output tests/artifacts/perf/20260603T-post-laplacian-reprofile/profile_normalized_laplacian_fnx.txt`
- `RCH_ENV_ALLOWLIST=PYTHONPATH rch exec -- env PYTHONPATH=python .venv/bin/python tests/artifacts/perf/20260602T-vs-upstream-sweep/bench_vs_upstream.py bench --case normalized_laplacian_default --impl fnx --n 8000 --m 4 --repeats 30`
- `hyperfine --warmup 2 --runs 8 'RCH_ENV_ALLOWLIST=PYTHONPATH rch exec -- env PYTHONPATH=python .venv/bin/python tests/artifacts/perf/20260602T-vs-upstream-sweep/bench_vs_upstream.py bench --case normalized_laplacian_default --impl fnx --n 8000 --m 4 --repeats 5'`

## Behavior Checks

- `RCH_ENV_ALLOWLIST=PYTHONPATH rch exec -- env PYTHONPATH=python .venv/bin/python -m py_compile python/franken_networkx/__init__.py`: passed.
- `RCH_ENV_ALLOWLIST=PYTHONPATH rch exec -- env PYTHONPATH=python .venv/bin/python -m pytest tests/python/test_spectral_ordering_parity.py tests/python/test_parity_comprehensive.py tests/python/test_to_scipy_sparse_default_native_parity.py -q -k 'normalized_laplacian or laplacian_matrix'`: `5 passed, 169 deselected`.
- Golden SHA: `aa810df87c3bc48287dcee99741e5a144bb8a4155d83a6d079520488b39769b8` across baseline FNX, NetworkX oracle, after FNX, and confirm.

## UBS

`timeout 180s ubs python/franken_networkx/__init__.py` exited `124` after printing the scanner banner and `Scanning python...`; no findings were emitted before the cap.
