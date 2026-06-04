# Validation Summary

Bead: `br-r37-c1-oymqq`

## Commands

Baseline and rebuild:

```bash
rch exec -- maturin develop --release --features pyo3/abi3-py310
rch exec -- .venv/bin/python tests/artifacts/perf/20260603T-next-residual-sweep/bench_sparse_dtype_none.py sample --case to_scipy_weighted --impl both --n 8000 --m 4 --seed 42 --repeats 15
rch exec -- .venv/bin/python tests/artifacts/perf/20260603T-next-residual-sweep/bench_sparse_dtype_none.py profile --case to_scipy_weighted --impl fnx --n 8000 --m 4 --seed 42 --repeats 11 --profile-output tests/artifacts/perf/20260603T-sparse-edge-attr-sync/profile_baseline_to_scipy_weighted_fnx.txt
rch exec -- hyperfine --warmup 5 --runs 25 --export-json tests/artifacts/perf/20260603T-sparse-edge-attr-sync/hyperfine_baseline_to_scipy_weighted.json 'env PYTHONPATH=python .venv/bin/python tests/artifacts/perf/20260603T-next-residual-sweep/bench_sparse_dtype_none.py sample --case to_scipy_weighted --impl fnx --n 8000 --m 4 --seed 42 --repeats 5 >/dev/null'
```

After validation:

```bash
rch exec -- cargo check -p fnx-python --features pyo3/abi3-py310
rch exec -- cargo clippy -p fnx-python --features pyo3/abi3-py310 -- -D warnings
rustfmt --edition 2024 --check crates/fnx-python/src/lib.rs crates/fnx-python/src/digraph.rs
.venv/bin/python -m py_compile python/franken_networkx/__init__.py
rch exec -- maturin develop --release --features pyo3/abi3-py310
rch exec -- .venv/bin/python -m pytest tests/python/test_to_scipy_sparse_native_weighted_parity.py -q
rch exec -- .venv/bin/python -m pytest tests/python/test_to_scipy_sparse_default_native_parity.py -q
rch exec -- .venv/bin/python tests/artifacts/perf/20260603T-next-residual-sweep/bench_sparse_dtype_none.py sample --case to_scipy_weighted --impl both --n 8000 --m 4 --seed 42 --repeats 15
rch exec -- .venv/bin/python tests/artifacts/perf/20260603T-next-residual-sweep/bench_sparse_dtype_none.py profile --case to_scipy_weighted --impl fnx --n 8000 --m 4 --seed 42 --repeats 11 --profile-output tests/artifacts/perf/20260603T-sparse-edge-attr-sync/profile_after_confirm_to_scipy_weighted_fnx.txt
rch exec -- hyperfine --warmup 5 --runs 25 --export-json tests/artifacts/perf/20260603T-sparse-edge-attr-sync/hyperfine_after_confirm2_to_scipy_weighted.json 'env PYTHONPATH=python .venv/bin/python tests/artifacts/perf/20260603T-next-residual-sweep/bench_sparse_dtype_none.py sample --case to_scipy_weighted --impl fnx --n 8000 --m 4 --seed 42 --repeats 5 >/dev/null'
timeout 180s ubs crates/fnx-python/src/lib.rs crates/fnx-python/src/digraph.rs tests/python/test_to_scipy_sparse_native_weighted_parity.py
```

## Results

- `cargo check`: passed.
- `cargo clippy`: passed with `-D warnings`.
- `rustfmt --check`: passed.
- Python compile: passed.
- Weighted sparse parity: `297 passed`.
- Default sparse parity: `7 passed`.
- UBS split Rust/test scan: `Critical: 0`, with pre-existing warning/info inventory.
- Full touched-file UBS attempt hit the 180s timeout during the generated Python module scan after Rust completed in 16s.

## Performance Gate

- Direct FNX mean: `0.014587645801172281s -> 0.012729135532087337s` (`1.146x`).
- Profile total: `0.184s -> 0.167s`.
- Sync frame: `0.032s -> 0.000s`.
- Hyperfine repeat mean: `0.8805329283399999s -> 0.8682897172999999s`.
- Golden CSR digest unchanged: `12d41580d0336461201dbaa08fecc5250eab75162c958f5a91da80875db1ab37`.

Decision: keep. Score `6.0`.

## Next Profile Target

After the edge-only sync removal, the residual profile is dominated by:

- `adjacency_default_order_typed_arrays`: `0.075s` over 12 calls.
- `numpy.asarray`: `0.051s` over 111 calls.
- SciPy COO to CSR conversion: `0.008s` over 12 calls.

The next optimization pass should attack the array handoff / direct CSR construction primitive, not another attr-sync micro-lever.
