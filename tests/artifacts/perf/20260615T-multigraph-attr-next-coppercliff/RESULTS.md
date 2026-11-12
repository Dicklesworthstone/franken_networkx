# br-r37-c1-nzyr4 Results

Target: `MultiGraph.add_edges_from([(u, v, {"weight": ...}), ...])` on a fresh exact-int graph.

Lever: add one fresh-graph, exact-`int`, per-edge-`dict` batch path that assigns NetworkX-compatible undirected multiedge keys before bulk-loading index-keyed edges into `fnx-classes`.

Mapped primitive: Alien Graveyard section 8.2, "Vectorized Execution + Morsel-Driven Parallelism". The local analogue is a batch operator across the Python/Rust boundary: process the whole edge vector once instead of paying the per-edge Python/PyO3 path.

## Baseline

- Direct survey, FNX median: `0.026685831020586193s`
- Direct survey, FNX mean: `0.03057044144305918s`
- Direct survey, FNX/NX ratio: `1.7268229239752055x`
- Hyperfine FNX mean: `2.17231775984s`
- Hyperfine FNX median: `2.16036592694s`
- Profile hot line: `_try_add_attr_edges_from_batch`, `2.124s / 80 loops`
- Golden digest: `50644c550f48ebc209b8fa5bb649acf1961385c2b71d65f0a572cb3e2a22ae99`

## After

- Direct survey, FNX median: `0.02006734296446666s`
- Direct survey, FNX mean: `0.025516237888950855s`
- Direct survey, FNX/NX ratio: `1.1970584440069563x`
- Hyperfine FNX mean: `1.7871700655799998s`
- Hyperfine FNX median: `1.7929829640800001s`
- Profile hot line: `_try_add_attr_edges_from_batch`, `1.456s / 80 loops`
- Golden digest: `50644c550f48ebc209b8fa5bb649acf1961385c2b71d65f0a572cb3e2a22ae99`

## Delta

- Direct survey median speedup: `1.33x`
- Direct survey mean speedup: `1.20x`
- Hyperfine mean speedup: `1.22x`
- Hyperfine median speedup: `1.20x`
- FNX/NX direct ratio: `1.7268x -> 1.1971x`
- FNX/NX hyperfine ratio: `1.3843x -> 1.1544x`
- Profile hot-line speedup: `1.46x`
- Score: Impact `3` x Confidence `4` / Effort `2` = `6.0`; keep.

## Isomorphism Proof

- Ordering preserved: node labels and Python node objects are collected in first-seen input order, then inserted in that order. Edge rows use the same undirected storage layout as the existing `MultiGraph` path.
- Tie-breaking unchanged: the fast path only handles fresh graphs, so auto keys are the NetworkX sequence `0, 1, 2, ...` per undirected pair. The pair counter uses the same string-label orientation as `EdgeKey::new`.
- Floating point: no arithmetic is performed. Float attributes are copied through the existing `py_dict_to_attr_map` converter.
- RNG: no RNG surface.
- Source dict aliasing: non-empty edge dicts are copied into fresh FNX-owned Python dict mirrors; mutating the caller's source dict after construction does not affect stored edge data.
- Fallbacks: bool endpoints, non-exact ints, non-dict third elements, global attrs, incompatible attrs, short batches, non-list/tuple iterables, and non-fresh graphs all return to the existing path.
- Golden output verification: `baseline_survey.json` and `after_survey.json` both report NetworkX/FNX digest match for `50644c550f48ebc209b8fa5bb649acf1961385c2b71d65f0a572cb3e2a22ae99`.

## Validation

- `rch exec -- cargo check -p fnx-classes -p fnx-python --all-targets --features pyo3/abi3-py310`
- `rch exec -- maturin develop --profile release-perf --features pyo3/abi3-py310`
- `rch exec -- env PYTHONPATH=python .venv/bin/python -m pytest tests/python/test_add_edges_attr_batch_parity.py -q` -> `25 passed`
- `cargo fmt --check`
- `rch exec -- cargo clippy -p fnx-classes -p fnx-python --all-targets --features pyo3/abi3-py310 -- -D warnings`
- `ubs crates/fnx-classes/src/lib.rs crates/fnx-python/src/lib.rs tests/python/test_add_edges_attr_batch_parity.py` -> exit `0`, no critical findings
