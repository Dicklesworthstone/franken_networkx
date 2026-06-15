# br-r37-c1-mfevj DiGraph Attr Exact-Weight Rejection

## Target

- Bead: `br-r37-c1-mfevj`
- Profile-backed hotspot: `DiGraph.add_edges_from([(u, v, {"weight": 1.0}), ...])`
- Candidate lever: reuse the existing exact `{"weight": float}` attr conversion helper inside the DiGraph fresh exact-int attributed batch collector.
- Alien-graveyard primitive lineage: vectorized/batched execution across the Python/Rust boundary. This candidate was a micro-specialization within that family, not the deeper structural replacement.

## Baseline

- Direct survey `digraph_attr`: FNX median `0.009758149972185493s`, mean `0.013263604778330773s`; NetworkX median `0.00898233096813783s`, mean `0.013482539435952075s`; FNX/NX median ratio `1.0863716786655548x`.
- Profile: `8018642 function calls in 5.419s`; `_digraph_attr` cumulative `1.462s / 120`; `_try_add_edges_from_batch` `0.912s / 120`.
- Hyperfine process envelope: FNX mean `2.22218066648s`, median `2.2370718593800003s`; NetworkX mean `1.59308258688s`, median `1.5847900208799999s`.
- Golden digest: `3f1de3be563f8e8f7a63710ca7bea1886888bd83417fcdade9249eee112d9d1c`.

## Candidate Result

- Direct survey after candidate: FNX median `0.009560117032378912s`, mean `0.010740181107798384s`; NetworkX median `0.0070732979802414775s`, mean `0.01263354221979777s`; FNX/NX median ratio `1.351578437538487x`.
- Profile after candidate: `8018642 function calls in 5.414s`; `_digraph_attr` cumulative `1.467s / 120`; `_try_add_edges_from_batch` `0.930s / 120`.
- Hyperfine after candidate: FNX mean `2.19709871462s`, median `2.19400813232s`; NetworkX mean `1.71769790952s`, median `1.70947837482s`.
- Golden digest remained `3f1de3be563f8e8f7a63710ca7bea1886888bd83417fcdade9249eee112d9d1c`; digests matched NetworkX before and after.

## Isomorphism Proof

- Ordering and tie-breaking: unchanged. The candidate only changed attr conversion for fresh exact-int DiGraph attributed batch collection; node first-seen order, directed edge insertion order, and duplicate last-write semantics remained delegated to the same collector/storage path.
- Floating point: unchanged. The candidate only accepted exact Python `float` values for the single key `weight` and produced the same `CgseValue::Float` plus Python mirror value as the existing generic converter.
- RNG: none used.
- Golden output: construction digest stayed identical at `3f1de3be563f8e8f7a63710ca7bea1886888bd83417fcdade9249eee112d9d1c`.

## Validation

- `rch exec -- cargo check -p fnx-python --all-targets --features pyo3/abi3-py310`
- `rch exec -- maturin develop --profile release-perf --features pyo3/abi3-py310`
- `rch exec -- env PYTHONPATH=python .venv/bin/python -m pytest tests/python/test_add_edges_attr_batch_parity.py -q` -> `26 passed`
- `cargo fmt --check`
- `rch exec -- cargo clippy -p fnx-python --all-targets --features pyo3/abi3-py310 -- -D warnings`
- `ubs crates/fnx-python/src/digraph.rs tests/python/test_add_edges_attr_batch_parity.py` -> exit `0`, no critical findings; warnings were broad pre-existing inventory.

## Score And Decision

- Impact `1` x Confidence `3` / Effort `2` = `1.5`.
- Decision: reject. This does not clear Score >= `2.0`; the targeted profile entry regressed slightly from `0.912s` to `0.930s`, and the process-level FNX mean improved only `1.1%`, inside noise.
- Code changes were reverted. This artifact keeps the profile-backed no-ship record.

## Next Primitive

- Attack a deeper DiGraph-specific batch attribute write primitive instead of repeating single-attr conversion tweaks.
- Target ratio: at least `1.5x` FNX self-speedup on `_try_add_edges_from_batch` by constructing Rust `AttrMap`s and Python mirrors in one batch allocation plan, preserving directed duplicate overwrite order and Python attr-copy isolation.
