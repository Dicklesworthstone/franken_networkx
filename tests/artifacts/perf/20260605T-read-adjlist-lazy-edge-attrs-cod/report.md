# perf: read_adjlist lazy edge-attribute mirrors (br-r37-c1-04z53.55)

## Target

Profile-backed residual from `20260605T-read-adjlist-native-cc`: the native
`read_adjlist_simple` path still allocated one empty Python edge-attribute dict
per attr-less edge. The existing `PyGraph::materialize_edge_py_attrs` already
creates that dict lazily on first Python access or mutation.

## Lever

Keep `edge_py_attrs` sparse while parsing adjacency-list files. The parser still
bulk-inserts the same nodes and edges in the same order; only the eager empty
edge-data mirror allocation is skipped.

## Baseline

Input: `/data/tmp/fnx_read_adjlist_lazy_attrs_20000_60247.adjlist`

- Nodes/edges: 20,000 / 60,247
- Input SHA256: `fef95211362a57977b529ceeef73474c663a1a12a7637ec7012f5a1f0ccd2a5b`
- Strict proof SHA before: `57661014bdb3eabc7bd3837d59c78d0849f0e7c334526ae7f716c9b8983d75a3`
- Internal string-path fnx best: `0.25129491899861023s/read`
- Internal string-path nx best: `0.0942986583977472s/read`
- RCH hyperfine fnx mean: `3.0212953106700007s`
- RCH hyperfine nx mean: `1.5207499602949999s`

The initial Path-object baseline in this directory is intentionally not used for
the keep gate; Path inputs miss the pre-existing string-only fast-path gate and
measure fallback delegation instead of `read_adjlist_simple`.

## Result

- Internal string-path fnx best: `0.1581737672968302s/read`
- Internal self-speedup: `1.5887269001251523x`
- Ratio vs nx best: `2.664883289629216x -> 1.7694926392391446x`
- RCH hyperfine fnx mean: `3.0212953106700007s -> 2.717859961605s`
- RCH hyperfine self-speedup: `1.1116449535118103x`
- cProfile native call total for 10 reads: `1.789s -> 1.362s`
- Graph digest unchanged: `7cffbb435e2f871b32267801fcb0da36d579e951b7d3e9279e349f211b664715`
- Strict golden SHA unchanged: `57661014bdb3eabc7bd3837d59c78d0849f0e7c334526ae7f716c9b8983d75a3`

Score: Impact `1.59` x Confidence `0.95` / Effort `0.45` = `3.36`; keep.

## Proof

- `cargo fmt --check`
- `rch exec -- cargo check -p fnx-python --all-targets`
- `rch exec -- cargo clippy -p fnx-python --all-targets -- -D warnings`
- `rch exec -- maturin develop --release --features pyo3/abi3-py310`
- `PYTHONPATH=python .venv/bin/python tests/artifacts/perf/20260605T-read-adjlist-lazy-edge-attrs-cod/adjlist_lazy_attrs.py proof --expect-sha 57661014bdb3eabc7bd3837d59c78d0849f0e7c334526ae7f716c9b8983d75a3`
- `PYTHONPATH=python .venv/bin/python -m pytest tests/python/test_read_adjlist_native_parity.py -q`
- `PYTHONPATH=python .venv/bin/python -m pytest tests/python/test_io.py -k adjlist -q`
- `PYTHONPATH=python .venv/bin/python -m pytest tests/python/test_adj_mapping_parity.py tests/python/test_copy_row_order_parity.py -q`
- `ubs --only=rust crates/fnx-python/src/readwrite.rs`
- `ubs --only=python tests/artifacts/perf/20260605T-read-adjlist-lazy-edge-attrs-cod/adjlist_lazy_attrs.py`

## Next Residual

After this pass the native parser remains slower than nx on the large file. The
next profile-backed primitive should attack the remaining string/canonical-id
and node-attribute mirror allocation substrate, not the edge-attribute mirror.
