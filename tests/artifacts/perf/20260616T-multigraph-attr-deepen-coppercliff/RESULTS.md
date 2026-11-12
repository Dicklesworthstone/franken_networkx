# br-r37-c1-04z53.9122 Results

Target: `MultiGraph.add_edges_from([(u, v, {"weight": 1.0}), ...])` on a fresh exact-int graph.

Lever: specialize the fresh exact-int keyed MultiGraph attributed batch for exact single `{"weight": float}` dicts, constructing the Rust `AttrMap` and Python mirror directly while retaining the generic converter fallback for every other attr shape.

Mapped primitive: Alien Graveyard section 8.2, vectorized/batched execution. This is a batch-lane specialization inside the existing Rust/PyO3 boundary crossing, avoiding repeated generic dictionary conversion for the measured monomorphic attr shape.

## Baseline

- Direct survey, FNX median: `0.019964146020356566s`
- Direct survey, FNX mean: `0.024204343476762567s`
- Direct survey, FNX/NX ratio: `1.3080776097874007x`
- Hyperfine FNX mean: `2.23043042064s`
- Hyperfine FNX median: `2.049519325s`
- Profile hot line: `_try_add_attr_edges_from_batch`, `3.073s / 160 loops`
- Golden digest: `50644c550f48ebc209b8fa5bb649acf1961385c2b71d65f0a572cb3e2a22ae99`

## After

- Direct survey, FNX median: `0.019436814996879548s`
- Direct survey, FNX mean: `0.023526858538389206s`
- Direct survey, FNX/NX ratio: `1.2230452538730272x`
- Hyperfine FNX mean: `1.8718418380599997s`
- Hyperfine FNX median: `1.8726079141s`
- Profile hot line: `_try_add_attr_edges_from_batch`, `2.830s / 160 loops`
- Golden digest: `50644c550f48ebc209b8fa5bb649acf1961385c2b71d65f0a572cb3e2a22ae99`

## Delta

- Hyperfine mean speedup: `1.1915699154110402x`
- Hyperfine median speedup: `1.0944732795199286x`
- Direct survey median speedup: `1.0271305264551664x`
- Direct survey mean speedup: `1.0287962346212902x`
- Profile hot-line speedup: `1.0858657243816255x`
- FNX/NX direct ratio: `1.3080776097874007x -> 1.2230452538730272x`
- Score: Impact `2.5` x Confidence `3` / Effort `2` = `3.75`; keep.

## Isomorphism Proof

- Ordering preserved: node labels and Python node objects are still collected in first-seen input order; edges are still appended in input order.
- Tie-breaking unchanged: the fast path only handles fresh exact-int MultiGraphs, so auto keys remain sequential per undirected pair. Pair orientation still uses the existing node-label ordering.
- Floating point: the fast path copies exact `PyFloat` values into `CgseValue::Float`; it performs no arithmetic and does not change NaN or signed-zero handling beyond the existing float extraction contract.
- RNG: no RNG surface.
- Source dict aliasing: the Python mirror is a fresh dict populated from the source key/value. `candidate_weight_float_golden.json` confirms mutating the input dict after construction does not change stored edge data.
- Fallbacks: non-singleton dicts, non-`weight` keys, non-float values, empty dicts, bool endpoints, non-exact ints, non-dict thirds, global attrs, non-fresh graphs, and incompatible values keep the previous generic/fallback paths.
- Golden output verification: `baseline_survey.json` and `after_survey.json` both report NetworkX/FNX digest match for `50644c550f48ebc209b8fa5bb649acf1961385c2b71d65f0a572cb3e2a22ae99`; `candidate_weight_float_golden.json` reports exact match for the single-weight float probe digest `97c8b7249d7598cb7699464cb16b39cdb67daacdd92847f9c60b9fc439e29934`.

## Validation

- `rch exec -- env CARGO_TARGET_DIR=/data/tmp/franken-networkx-check-9122 cargo check -p fnx-python --all-targets --features pyo3/abi3-py310`
- `rch exec -- env CARGO_TARGET_DIR=/data/tmp/franken-networkx-maturin-9122 .venv/bin/maturin develop --profile release-perf --features pyo3/abi3-py310`
- `rch exec -- env PYTHONPATH=python .venv/bin/python -m pytest tests/python/test_add_edges_attr_batch_parity.py -q` -> `25 passed`
- `cargo fmt --check`
- `rch exec -- env CARGO_TARGET_DIR=/data/tmp/franken-networkx-clippy-9122 cargo clippy -p fnx-python --all-targets --features pyo3/abi3-py310 -- -D warnings`
- `ubs crates/fnx-python/src/lib.rs` -> exit `0`, no critical findings; existing warning inventory only.
