# br-r37-c1-fwm0j MultiDiGraph Attr Capacity Rejection

## Target

- Bead: `br-r37-c1-fwm0j`
- Profile-backed residual: `MultiDiGraph.add_edges_from([(u, v, {"weight": 1.0}), ...])`.
- Candidate lever: pre-size the fresh exact-int MultiDiGraph keyed attributed collector, Python mirror maps, and Rust `MultiDiGraph` storage.

## Baseline

- Direct survey `multidigraph_attr`: FNX median `0.018613846972584724s`, mean `0.022833328551819757s`; NetworkX median `0.01738386700162664s`, mean `0.03357409421975414s`; FNX/NX median ratio `1.0707541061400776x`.
- Profile: `9939842 function calls in 7.000s`; `_multidigraph_attr` cumulative `2.627s / 120`; `_try_add_edges_from_batch` `0.010s / 120`.
- Hyperfine process envelope: FNX mean `2.6919843335799998s`, median `2.6853173264800003s`; NetworkX mean `2.33047156698s`, median `2.30131583098s`.
- Golden digest: `58267b72563bb3af74585c8d9d4e4dc2e46cbb5f253675efdebda5ea12604b24`.

## Candidate Result

- Direct survey after candidate: FNX median `0.019643146020825952s`, mean `0.025160644539735384s`; NetworkX median `0.017107521009165794s`, mean `0.031042492663901713s`; FNX/NX median ratio `1.148216974879156x`.
- Profile after candidate: `9939842 function calls in 7.097s`; `_multidigraph_attr` cumulative `2.612s / 120`; `_try_add_edges_from_batch` still `0.010s / 120`.
- Hyperfine after candidate: FNX mean `2.9948464625199995s`, median `2.88163763062s`; NetworkX mean `2.5661996981199997s`, median `2.56761156312s`.
- Golden digest stayed `58267b72563bb3af74585c8d9d4e4dc2e46cbb5f253675efdebda5ea12604b24`.

## Isomorphism Proof

- Ordering and tie-breaking: unchanged in the candidate. It only changed allocation capacities; traversal order, first-seen node order, and per-pair key numbering used the same collector logic.
- Attribute semantics: unchanged. The same attr conversion and Python mirror insertion paths were used.
- Floating point: unchanged; `{"weight": 1.0}` still used the same exact-float fast path already present for MultiDiGraph.
- RNG: none used.
- Golden output: digest stayed `58267b72563bb3af74585c8d9d4e4dc2e46cbb5f253675efdebda5ea12604b24`.

## Validation

- `cargo fmt --check`
- `rch exec -- cargo check -p fnx-classes -p fnx-python --all-targets --features pyo3/abi3-py310`
- `rch exec -- env CARGO_TARGET_DIR=/data/tmp/franken-networkx-maturin-fwm0j .venv/bin/maturin develop --profile release-perf --features pyo3/abi3-py310`
- `rch exec -- env PYTHONPATH=python .venv/bin/python -m pytest tests/python/test_add_edges_attr_batch_parity.py -q` -> `25 passed`

## Score And Decision

- Impact `0` x Confidence `4` / Effort `1` = `0.0`.
- Decision: reject. Direct FNX median regressed `18.614ms -> 19.643ms`, hyperfine FNX mean regressed `2.692s -> 2.995s`, and the profiled `_try_add_edges_from_batch` entry was unchanged at `0.010s / 120`.
- Code changes were reverted.

## Residual

- MultiDiGraph attr construction is not bottlenecked in `_try_add_edges_from_batch`; the visible residual is dominated by surrounding Python construction/digest path costs. Do not repeat capacity tuning here. The next MultiDiGraph attack needs a different primitive, likely edge-data materialization or Python wrapper loop removal, with a narrower profile first.
