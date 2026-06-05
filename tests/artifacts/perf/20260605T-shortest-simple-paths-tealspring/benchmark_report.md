# br-r37-c1-1bcb7 benchmark report

## Command

`rch exec -- hyperfine --warmup 3 --runs 10 --export-json ...`

All benchmark commands reused a constructed graph across loop iterations and consumed the same bounded prefix from the generator.

## Results

| Case | Before mean | After mean | Speedup |
| --- | ---: | ---: | ---: |
| `fnx path_2000_first1`, loops 20 | 0.558363751s | 0.385829377s | 1.447x |
| `fnx cycle_2000_first2`, loops 10 | 0.523533596s | 0.420212188s | 1.246x |

Baseline comparator candidate (`direct`) predicted the same lever:

| Case | Baseline current | Baseline direct candidate | Candidate speedup |
| --- | ---: | ---: | ---: |
| `path_2000_first1`, loops 20 | 0.558363751s | 0.390676371s | 1.429x |
| `cycle_2000_first2`, loops 10 | 0.523533596s | 0.441404018s | 1.186x |

## Validation

- `rch exec -- maturin develop --release --features pyo3/abi3-py310`: pass
- `python3 -m py_compile python/franken_networkx/__init__.py tests/python/test_shortest_simple_paths_msg_parity.py shortest_simple_paths_bench.py`: pass
- `python3 -m pytest tests/python/test_shortest_simple_paths_msg_parity.py tests/python/test_simple_paths_conformance.py tests/python/test_astar_yen.py tests/python/test_traversal_generator_parity.py tests/python/test_path_generator_validation_parity.py tests/python/test_simple_paths_module_parity.py tests/python/test_graphical_operators_paths_conformance.py -q`: 349 passed
- `rch exec -- cargo check -p fnx-python --all-targets`: pass
- `rch exec -- cargo clippy -p fnx-python --all-targets -- -D warnings`: pass
- `cargo fmt -p fnx-python --check`: pass
- `git diff --check` on touched files: pass
- `ubs` on touched Python files: timed out at 180s while scanning; see `ubs_touched.exit` (`124`) and `ubs_touched.log`

## Score

Impact 3 x Confidence 4 / Effort 2 = 6.0. Keep threshold is 2.0.

## Next profile target

This removes the conversion tax. The after profile now spends time in NetworkX Yen over the fnx neighbor facade, especially `neighbors`, `_has_networkx_private_storage`, and `_private_override`.

The next deeper primitive is a native lazy Yen generator for simple unweighted fnx graphs: direct predecessor/successor search over indexed graph storage with NetworkX-compatible path ordering and exception timing. Target ratio: at least another 2x on `path_2000_first1` by removing Python neighbor-facade calls while keeping the generator contract.
