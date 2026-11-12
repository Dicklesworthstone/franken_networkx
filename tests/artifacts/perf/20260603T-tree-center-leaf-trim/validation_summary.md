# Validation Summary: tree center leaf trimming

## Commands
- `rch exec -- env PYTHONPATH=python .venv/bin/python -m py_compile python/franken_networkx/__init__.py tests/python/test_center_periphery_order_parity.py tests/artifacts/perf/20260603T-tree-center-leaf-trim/bench_tree_distance.py`: passed
- `rch exec -- env PYTHONPATH=python .venv/bin/python -m pytest tests/python/test_center_periphery_order_parity.py tests/python/test_distance_measures_conformance.py tests/python/test_distance_cross_type.py -q -k 'center or radius or periphery or diameter'`: `817 passed, 122 deselected`
- `ubs tests/python/test_center_periphery_order_parity.py tests/artifacts/perf/20260603T-tree-center-leaf-trim/bench_tree_distance.py`: exit `0`
- `ubs --only=python python/franken_networkx/__init__.py`: timed out at the 180s cap on the generated module; no finding was emitted before timeout.

## Behavior
Center and all-output SHA values stayed unchanged against NetworkX. The regression test monkeypatches `fnx.eccentricity` to prove tree `center` no longer depends on the general eccentricity path.

## Notes
NetworkX 3.6.1 uses the tree leaf-trimming primitive for `center` only. `radius`, `periphery`, and `diameter` keep their previous FNX paths in this lever.
