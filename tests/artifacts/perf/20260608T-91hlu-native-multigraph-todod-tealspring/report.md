# br-r37-c1-91hlu: native MultiGraph to_dict_of_dicts result construction

## Target

After `br-r37-c1-rup1h`, `to_dict_of_dicts(MultiGraph/MultiDiGraph)` still rebuilt the output rows in Python for every default-nodelist call. The profile showed repeated PyO3 row-view calls plus hundreds of thousands of Python cache lookups across 80 calls.

This pass keeps the row-stamped `_LiveMultiEdgeDataView` cache and moves only the default-nodelist, `edge_data is None`, exact `MultiGraph` / `MultiDiGraph` result-dict construction into PyO3. Custom nodelists and `edge_data` overrides keep the existing Python path.

## Baseline

- Direct `MultiGraph`: `0.17068480199668556s`, FNX/NX ratio `13.856897455882587`
- Direct `MultiDiGraph`: `0.12028453103266656s`, FNX/NX ratio `10.92639709685283`
- Hyperfine `MultiGraph` mean: `0.6615761184400001s`
- Hyperfine `MultiDiGraph` mean: `0.5793214092200001s`
- Profile `to_dict_of_dicts`: `0.576s` cumulative for `MultiGraph`; `0.433s` cumulative for `MultiDiGraph`

## Lever

Added `_native_to_dict_of_dicts_live` on both exact multigraph PyO3 classes. The helper walks canonical node order and neighbor/successor order in Rust, builds Python row dicts directly, and gets or creates `_LiveMultiEdgeDataView` instances from the existing mutation-stamped row cache.

The Python router calls the helper only when:

- `type(G) is MultiGraph` or `type(G) is MultiDiGraph`
- `nodelist is None`
- `edge_data is None`

## After

- Direct `MultiGraph`: `0.17068480199668556s -> 0.09962635498959571s` (`1.714x`)
- Direct `MultiDiGraph`: `0.12028453103266656s -> 0.05339486396405846s` (`2.253x`)
- Hyperfine `MultiGraph`: `0.6615761184400001s -> 0.56937075284s` (`1.162x`)
- Hyperfine `MultiDiGraph`: `0.5793214092200001s -> 0.50049108072s` (`1.158x`)
- Profile `to_dict_of_dicts`: `0.576s -> 0.090s` for `MultiGraph`; `0.433s -> 0.059s` for `MultiDiGraph`

## Proof

- Proof payload SHA: `6d4ca0dcb1016f6a5ff02c2140f02a236eeff7f0bdabebe19ec09cf0f9bc26c8`
- Default `MultiGraph` content SHA stayed equal to NetworkX: `b1b747752c67181bc0cd66916756e146dfe00d25838bfecd2b9f45afbbb8af50`
- Default `MultiDiGraph` content SHA stayed equal to NetworkX: `759500ca11fcebe3ebab25ea7dd0e09a81a910e6fad4669a00822f63141eef63`
- Known undirected alias delta stayed `-12000`
- Custom `nodelist`, `edge_data`, hash-equal display-key cases, live attr mutation, mutation invalidation, read-only guards, deepcopy, and pickle passed
- Floating point: N/A
- RNG: N/A

## Gates

- `rustfmt --edition 2024 --check crates/fnx-python/src/lib.rs crates/fnx-python/src/digraph.rs`
- `python3 -m py_compile python/franken_networkx/__init__.py`
- `rch exec -- cargo check -p fnx-python --all-targets --features pyo3/abi3-py310`
- `rch exec -- cargo clippy -p fnx-python --all-targets --features pyo3/abi3-py310 -- -D warnings`
- `rch exec -- maturin develop --release --features pyo3/abi3-py310`
- `pytest tests/python/test_adj_mapping_parity.py tests/python/test_view_pickle_parity.py tests/python/test_copy_row_order_parity.py tests/python/test_from_dict_of_dicts_batch_parity.py -q` (`386 passed`)
- `git diff HEAD --check`
- `ubs crates/fnx-python/src/lib.rs crates/fnx-python/src/digraph.rs tests/artifacts/perf/20260608T-91hlu-native-multigraph-todod-tealspring/report.md` exited `0` with no critical findings. UBS including `python/franken_networkx/__init__.py` exceeded three minutes after Rust completed without emitted Python findings and was stopped.

Score: `3.8` (`Impact 3.8 * Confidence 4 / Effort 4`). Keep.

Residual route: the remaining 8.3x/5.1x ratio needs a graph-owned row/result cache or persistent keydict mirror primitive, not another Python branch-shape pass.
