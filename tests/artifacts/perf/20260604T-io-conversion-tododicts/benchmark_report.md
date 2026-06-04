# br-r37-c1-p4mqd to_dict_of_dicts Benchmark Report

Target: profile-backed `to_dict_of_dicts` residual from the IO/conversion
slow-path sweep on an attr-less exact `Graph`.

Lever kept: the native `_fnx.to_dict_of_dicts_undirected` builder now inserts
borrowed live edge-attribute dictionaries directly into the result dict instead
of cloning a `Py<PyDict>` handle for every edge before `set_item`. `set_item`
already retains the value, so the extra handle clone was redundant.

## Baseline

- Harness: `bench_tododicts.py`
- Sweep: `baseline_sweep.jsonl`
- FNX mean: `0.0005403801744871932s`
- NetworkX mean: `0.00006293536805570488s`
- FNX / NX: `8.587x`
- cProfile: `_fnx.to_dict_of_dicts_undirected` `0.043s / 80 calls`
- Hyperfine: `312.1 ms +/- 22.8 ms`
- Golden SHA: `e5ca20d03e60a17015b200cf14d334af98ef21bdef44b1407a1916e66e156760`

## After

- Sweep: `after_sweep.jsonl`
- FNX mean: `0.00031222083049303875s`
- NetworkX mean: `0.00009234645829831319s`
- FNX / NX: `3.381x`
- cProfile: `_fnx.to_dict_of_dicts_undirected` `0.025s / 80 calls`
- Hyperfine: `313.2 ms +/- 25.0 ms`
- Golden SHA: `e5ca20d03e60a17015b200cf14d334af98ef21bdef44b1407a1916e66e156760`

## Delta

- In-process FNX speedup: `1.731x`
- Native cProfile frame speedup: `1.720x`
- Process hyperfine: unchanged because this target is sub-millisecond and
  Python startup dominates the command.
- Score: Impact `1` x Confidence `5` / Effort `2` = `2.5`

## Validation

- `rch exec -- cargo fmt --package fnx-python -- --check`
- `rch exec -- cargo check -p fnx-python --features pyo3/abi3-py310 --all-targets`
- `rch exec -- cargo clippy -p fnx-python --features pyo3/abi3-py310 --all-targets -- -D warnings`
- `rch exec -- maturin develop --release --features pyo3/abi3-py310`
- `rch exec -- env PYTHONPATH=python .venv/bin/python -m py_compile bench_tododicts.py`
- `rch exec -- env PYTHONPATH=python .venv/bin/python -m pytest tests/python/test_conversion.py::TestDictOfDicts -q`
- `ubs crates/fnx-python/src/readwrite.rs bench_tododicts.py`: exit 0, 0 critical findings.

