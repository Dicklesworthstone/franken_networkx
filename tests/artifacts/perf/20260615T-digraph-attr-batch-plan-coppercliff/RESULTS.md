# br-r37-c1-ijme6 DiGraph Attr Batch Allocation Plan

## Target

- Bead: `br-r37-c1-ijme6`
- Profile-backed hotspot: `DiGraph.add_edges_from([(u, v, {"weight": 1.0}), ...])` fresh exact-int attributed batch path.
- Lever: pre-size the known-batch allocations in the DiGraph exact-int attributed collector, Python node/edge mirror maps, and fresh Rust `DiGraph` `IndexMap` stores before inserting thousands of nodes and edges.
- Alien-graveyard primitive lineage: vectorized/batched execution across a language boundary, using one up-front allocation plan instead of growth-by-rehash during batch ingestion.

## Baseline

- Direct survey `digraph_attr`: FNX median `0.009839150006882846s`, mean `0.011134657349127034s`; NetworkX median `0.007267296023201197s`, mean `0.013604216342274513s`; FNX/NX median ratio `1.353894209823142x`.
- Profile: `8018642 function calls in 5.734s`; `_digraph_attr` cumulative `1.529s / 120`; `_try_add_edges_from_batch` `0.950s / 120`.
- Hyperfine process envelope: FNX mean `2.1509238786399996s`, median `2.16686110994s`; NetworkX mean `1.81674591684s`, median `1.7022815599399999s`.
- Golden digest: `3f1de3be563f8e8f7a63710ca7bea1886888bd83417fcdade9249eee112d9d1c`.

## After

- Direct survey `digraph_attr`: FNX median `0.008615176018793136s`, mean `0.008687129787479838s`; NetworkX median `0.006564629962667823s`, mean `0.011445267442872541s`; FNX/NX median ratio `1.3123627786770153x`.
- Direct FNX median speedup: `1.142x`.
- Profile: `8018642 function calls in 5.603s`; `_digraph_attr` cumulative `1.458s / 120`; `_try_add_edges_from_batch` `0.860s / 120`.
- Profiled hotspot speedup: `1.105x` on `_try_add_edges_from_batch`.
- Hyperfine process envelope: FNX mean `2.1349675133s`, median `2.1341789447s`; NetworkX mean `1.7311461220000002s`, median `1.7069983132000002s`. The process envelope is startup/digest dominated, so this is supporting evidence rather than the primary keep signal.
- Golden digest stayed `3f1de3be563f8e8f7a63710ca7bea1886888bd83417fcdade9249eee112d9d1c`.

## Isomorphism Proof

- Ordering and tie-breaking: unchanged. The collector still walks `ebunch_to_add` in the same order; node indices remain first-seen order; Rust storage still inserts directed edges in first edge order and merges duplicate attrs in the existing path.
- Attribute semantics: unchanged. `py_dict_to_attr_map_with_mirror` still converts every source dict; source dict non-aliasing, Python mirror live-dict behavior, and duplicate attr update semantics are unchanged.
- Floating point: unchanged. The same `CgseValue::Float` conversion path handles `{"weight": 1.0}` before and after.
- RNG: none used.
- Golden output: construction digest stayed `3f1de3be563f8e8f7a63710ca7bea1886888bd83417fcdade9249eee112d9d1c`.

## Validation

- `cargo fmt --check`
- `rch exec -- cargo check -p fnx-classes -p fnx-python --all-targets --features pyo3/abi3-py310`
- `rch exec -- env CARGO_TARGET_DIR=/data/tmp/franken-networkx-maturin-ijme6 .venv/bin/maturin develop --profile release-perf --features pyo3/abi3-py310`
- `rch exec -- env PYTHONPATH=python .venv/bin/python -m pytest tests/python/test_add_edges_attr_batch_parity.py -q` -> `25 passed`
- `rch exec -- cargo clippy -p fnx-classes -p fnx-python --all-targets --features pyo3/abi3-py310 -- -D warnings`
- `ubs crates/fnx-classes/src/digraph.rs crates/fnx-python/src/digraph.rs tests/python/test_add_edges_attr_batch_parity.py` -> exit `0`, no critical findings; warnings are broad pre-existing inventory.

## Score

- Impact `2` x Confidence `4` / Effort `1` = `8.0`; keep.

## Residual

- The capacity-growth tax is reduced, but the remaining `DiGraph` attributed construction gap is now dominated by per-edge Python tuple/dict traversal, PyDict mirror construction, and Rust/Python string key materialization. Next deeper attack should replace per-edge attr mirror construction with a batch mirror plan or a zero-copy/lazy mirror substrate that still preserves live edge-data dict behavior.
