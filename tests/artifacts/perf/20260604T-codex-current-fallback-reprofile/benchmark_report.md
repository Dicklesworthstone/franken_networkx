# br-r37-c1-nndbr to_dict_of_dicts Edge-Major Residual

Target: profile-backed exact simple `Graph` `to_dict_of_dicts` residual after
the prior PyDict handle clone fix. Current-head fallback reprofile on
2026-06-04 found FNX mean `0.0006656720815226435s` vs NetworkX mean
`0.0000957626849412918s` on the `n=800`, fanout 4 ring fixture.

Lever kept: the exact undirected native builder now pre-allocates the outer
node dicts in node insertion order, then fills per-node neighbor dicts by
walking storage-order edges once. This removes the old per-orientation
`neighbors_iter(u)` traversal and canonical edge-key lookup while preserving
the same live edge-attribute dict objects.

## Baseline

- Profile source: `current_residual_sweep.jsonl`
- FNX direct mean: `0.0006656720815226435s`
- FNX direct median: `0.0006483879988081753s`
- FNX / NetworkX: `6.951267938349264x`
- cProfile: `_fnx.to_dict_of_dicts_undirected` `1.369s / 2000 calls`
- Hyperfine: `4.3163344082199995s +/- 1.4388310211301831s`
- Hyperfine median: `3.3858945692199995s`

## After

- FNX direct mean: `0.0006141570529767446s`
- FNX direct median: `0.0005838759825564921s`
- FNX / NetworkX: `2.6430004941323273x`
- cProfile: `_fnx.to_dict_of_dicts_undirected` `0.687s / 2000 calls`
- Hyperfine: `2.1786210991366666s +/- 0.04858422777839926s`
- Hyperfine median: `2.17203594272s`
- Golden artifact SHA256: `4813ccf96ff53095332448d1c5f10c948df602557a0794468b89ae6e21edb3aa`

## Delta

- Direct FNX mean speedup: `1.0838792427705777x`
- Direct FNX median speedup: `1.1104892445981738x`
- Native cProfile frame speedup: `1.9927219796215428x`
- Hyperfine mean speedup: `1.9812230818523036x`
- Hyperfine median speedup: `1.5588575228547585x`
- Score: Impact `2` x Confidence `4` / Effort `2` = `4.0`

## Validation

- `cargo fmt -p fnx-python --check`
- `rch exec -- cargo check -p fnx-python --features pyo3/abi3-py310 --all-targets`
- `rch exec -- cargo clippy -p fnx-python --features pyo3/abi3-py310 --all-targets -- -D warnings`
- `rch exec -- maturin develop --release --features pyo3/abi3-py310`
- `rch exec -- python -m pytest tests/python/test_conversion.py -q -k 'DictOfDicts or to_dict_of_dicts'`
- `ubs crates/fnx-python/src/readwrite.rs`: exit 0, no critical findings.
