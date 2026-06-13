# br-r37-c1-04z53.80 - MultiGraph Lazy Edge Attr Mirrors

Note: this proof directory was created while the local work item was
`br-r37-c1-04z53.78`; upstream used `.78` for a generator residual before this
commit landed, and upstream then used `.79` for a generator residual, so the
final Beads closeout is `br-r37-c1-04z53.80`.

## Profile Target

After `br-r37-c1-04z53.77`, exact fresh
`MultiGraph.add_edges_from(8000 2-tuples, weight=1)` no longer used the Python
per-edge fallback, but cProfile moved the residual into
`_try_add_attr_edges_from_batch`. The baseline profile spent `0.394s` of
`0.395s` over 20 constructions in that native helper.

## Lever

Store the global-only edge attributes in the Rust `AttrMap` during exact fresh
2-tuple `MultiGraph` batch construction and skip eager Python `PyDict` mirrors.
When a NetworkX-observable edge-attr mapping is handed out, hydrate the live
dict from the stored `AttrMap` and preserve subsequent dict identity/mutation
semantics.

## Behavior Proof

- Golden file SHA unchanged:
  `cf9ac16652d5cc7f87ff7a8c206abd475b524af966e779015fc56bbc61c70fda`
- Embedded semantic SHA unchanged:
  `007468683edb7630f00c7d42429087ea13177e8d6e0f3588cf650d39b9eadee9`
- Construction digest unchanged:
  `c34547d2882e92ecff188201d9be2c41c5d7d2e0caeac70f23f07bc490f204d8`
- Post-rebase regenerated candidate golden was byte-identical to
  `candidate_golden.json`.
- Ordering and tie-breaking: node order, multiedge key assignment, undirected
  pair folding, edge iteration order, and adjacency row key order are recorded
  in the golden signature.
- Attribute semantics: global attrs, per-edge override precedence, explicit-key
  fallback, `get_edge_data`, `G[u][v][key]` identity, mutation persistence,
  `copy()`, and `to_directed()` are covered.
- Floating point: weighted `size`, `degree`, and edge data projections read the
  same numeric attrs; no arithmetic order was changed.
- RNG: no RNG path touched.

## Benchmark

Direct `rch` harness, 2000 nodes / 8000 multiedges / 60 loops / 9 repeats:

- FNX median: `0.03626599560011527s -> 0.022725871716587184s`
- Speedup: `1.5958021787848695x`
- NetworkX median in same runs: `0.015301542333327233s` baseline,
  `0.01371069345016925s` candidate
- FNX/NX ratio: `0.42192533474190896 -> 0.6033077023911068`

Hyperfine, 30 constructions per process:

- Mean: `1.0976255080600001s -> 0.9577003157600001s`
- Speedup: `1.1461054047883026x`

cProfile, 20 constructions:

- `_try_add_attr_edges_from_batch`: `0.394s -> 0.357s`
- Total calls stayed `141`; the win is from skipping eager mirror allocation.

## Validation

- `rch exec -- cargo check -p fnx-python --lib`: passed after rebase.
- `rch exec -- maturin build --release --features pyo3/abi3-py310`: passed after
  rebase; fresh wheel used to refresh the generated local extension for pytest.
- `PYTHONPATH=python pytest tests/python/test_attribute_access_parity.py -q`:
  `144 passed`.
- `python3 -m py_compile bench_mg_lazy_attrs.py`: passed.
- `git diff --check HEAD`: passed.
- `ubs crates/fnx-python/src/lib.rs bench_mg_lazy_attrs.py`: passed after the
  harness switched digest equality to `hmac.compare_digest`; remaining output is
  warnings/info only.
- `rustfmt --edition 2024 --check crates/fnx-python/src/lib.rs`: blocked by
  pre-existing formatting drift in unrelated regions/files.
- `rch exec -- cargo clippy -p fnx-python --lib -- -D warnings`: blocked by
  pre-existing `fnx-generators` unused-return errors at lines 538, 621, 666,
  6218, and 6758. `rch` attempted remote execution but failed open locally due
  an SSH reset before hitting the same errors.

## Score

Impact `1.5958` x Confidence `4` / Effort `2` = `3.19`.

Verdict: keep.
