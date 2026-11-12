# MultiDiGraph Attributed Batch Fast Path

Bead: `br-r37-c1-04z53.9115`

Target: `MultiDiGraph.add_edges_from([(u, v, {"weight": float}), ...])` exact-int fresh-edge attributed construction.

## Profile-Backed Baseline

- `baseline_profile_fnx.txt`: `_try_add_attr_edges_from_batch` accounted for 1.625s over 80 profiled builds, 20.31ms per build.
- `baseline_hyperfine.json`: FNX mean 1.7742s, median 1.7756s; NX mean 1.6613s, median 1.6343s.
- `baseline_survey.json`: FNX median 24.21ms, mean 28.98ms; NX median 19.82ms, mean 37.45ms; FNX/NX median ratio 1.2215.
- Baseline golden digest: `58267b72563bb3af74585c8d9d4e4dc2e46cbb5f253675efdebda5ea12604b24`.

## One Lever

Add a narrow Rust-side conversion fast path for one-item edge-attribute dictionaries whose exact key is the Python `str` `"weight"` and whose exact value is a Python `float`, only in `PyMultiDiGraph::collect_fresh_exact_int_attr_edge_batch`.

All other attribute shapes keep the existing `py_dict_to_attr_map_with_mirror` fallback.

## After

- `after_confirm_profile_fnx.txt`: `_try_add_attr_edges_from_batch` accounted for 3.146s over 160 profiled builds, 19.66ms per build.
- `after_confirm_hyperfine.json`: FNX mean 1.6377s, median 1.6230s; NX mean 1.5159s, median 1.5252s.
- `after_confirm_survey.json`: FNX median 21.21ms, mean 27.05ms; NX median 15.58ms, mean 17.03ms; FNX/NX median ratio 1.3615.
- After golden digest: `58267b72563bb3af74585c8d9d4e4dc2e46cbb5f253675efdebda5ea12604b24`.

FNX delta:

- Hyperfine mean: 1.7742s -> 1.6377s, 1.083x faster.
- Hyperfine median: 1.7756s -> 1.6230s, 1.094x faster.
- Survey median: 24.21ms -> 21.21ms, 1.141x faster.
- Profiled native batch frame: 20.31ms -> 19.66ms per build, 1.033x faster.

## Isomorphism Proof

- Ordering: the fast path runs inside the existing batch collector and does not reorder nodes, edge endpoints, edge keys, or insertion calls.
- Tie-breaking: per-pair key allocation remains in the existing MultiDiGraph storage path; this change only changes how one supported attribute map is converted before insertion.
- Fallbacks: non-dict third tuple items, bool/int mixed nodes, non-exact string keys, non-`"weight"` keys, non-exact floats, multi-item dictionaries, and conversion errors all use the prior fallback or prior batch rejection path.
- Mutation semantics: the Python mirror dictionary is still freshly allocated and populated from the source key/value objects, so later mutation of the source attribute dict remains non-aliasing.
- Floating point: the value is copied with `extract::<f64>()` into `CgseValue::Float`, matching the old generic converter for exact Python floats; no arithmetic, rounding, or comparisons were added.
- RNG: no randomness is introduced or consumed.
- Golden output: survey digest stayed `58267b72563bb3af74585c8d9d4e4dc2e46cbb5f253675efdebda5ea12604b24`.

## Validation

- `rch exec -- cargo check -p fnx-python --all-targets --features pyo3/abi3-py310`: pass before the final format-only wrap.
- `rch exec -- cargo clippy -p fnx-python --all-targets --features pyo3/abi3-py310 -- -D warnings`: pass.
- `cargo fmt --check`: pass.
- `rch exec -- maturin develop --profile release-perf --features pyo3/abi3-py310`: pass.
- `rch exec -- env PYTHONPATH=python .venv/bin/python -m pytest tests/python/test_add_edges_attr_batch_parity.py -q`: `23 passed`.
- `ubs crates/fnx-python/src/digraph.rs tests/python/test_add_edges_attr_batch_parity.py`: exit 0, no critical findings.
- `rch exec -- cargo test -p fnx-python --features pyo3/abi3-py310`: unrelated existing failure in `algorithms::tests::python_algorithm_wrappers_preserve_mode` comparing runtime policy decision-log order/timestamps; all other Rust tests in that crate passed.

## Score

Impact 2 x Confidence 3 / Effort 2 = 3.0. Kept.
