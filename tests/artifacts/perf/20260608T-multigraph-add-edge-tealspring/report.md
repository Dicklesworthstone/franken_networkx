# MultiDiGraph Fresh Keyed Add-Edge Fast Path

Bead: `br-r37-c1-04z53.60`
Baseline source: `c9d2aa002`
Agent: `TealSpring`

## Profile-backed target

Fresh residual profiling on current main found the largest constructor/add-loop gap in MultiGraph/MultiDiGraph add-edge loops. The target row was:

- `multidirected add_loop keyed`: FNX best `0.0825087256768408s`, NetworkX best `0.019199413829483092s`, ratio `4.297460662582228x`.
- cProfile for the harness showed `280000` Python `add_edge` calls dominating; the `MultiDiGraph.add_edge` wrapper alone accounted for `1.164s` cumulative before this pass.

Artifacts:

- `../20260608T-residual-scoreboard-tealspring/current_multigraph_ctor_bench_c9d2aa002.json`
- `../20260608T-residual-scoreboard-tealspring/current_multigraph_ctor_profile_c9d2aa002.txt`
- `../20260608T-residual-scoreboard-tealspring/current_multigraph_ctor_proof_c9d2aa002.json`

## Lever

One lever only: a guarded fast path for `MultiDiGraph.add_edge(u, v, key=...)` when all of these are true:

- `u` and `v` are exact Python `int` objects representable by the existing canonical integer node path.
- `key` is an exact non-negative `int` representable as `usize`, or an exact `str`.
- no edge attributes are supplied.
- the directed `(u, v)` edge bucket is fresh.
- stored display objects do not conflict with the passed endpoint objects.

All duplicate-key, existing-pair, attribute, negative/big integer key, non-exact object, and display-conflict cases fall back to the previous generic path.

## Benchmark

Focused same-target hyperfine, wrapped with `rch exec`:

- baseline mean `1.828050105015s`, stddev `0.09665051048299624s`
- after mean `1.406042125175s`, stddev `0.08053461799734973s`
- speedup `1.300139x`

Broad sweep target row:

- baseline FNX best `0.0825087256768408s`, NetworkX best `0.019199413829483092s`, ratio `4.297460662582228x`
- after FNX best `0.06798587266045313s`, NetworkX best `0.01822215351664151s`, ratio `3.730946103508817x`
- broad-row speedup `1.213616x`

Artifacts:

- `baseline_multidirected_add_loop_keyed_hyperfine.json`
- `after_multidirected_add_loop_keyed_hyperfine.json`
- `after_multigraph_ctor_bench_c9d2aa002.json`
- `after_multigraph_ctor_profile_c9d2aa002.txt`

## Isomorphism proof

Golden SHA before and after:

`1e2307714d33f155f34378b7d6e76c3d8d6b62cb4be4f16b9242711fed894531`

The proof covers `MultiGraph` and `MultiDiGraph` node order, successor/predecessor or neighbor order, edge key order, duplicate-key update order, copy, pickle, live edge-data mutation, exact int/string keyed constructor surfaces, and current display-conflict behavior. Focused pytest additionally covers exact keyed `MultiDiGraph.add_edge` order and negative integer key fallback against NetworkX.

Floating point: no algorithmic floating-point output is changed. Numeric display-conflict behavior remains on the existing fallback surface.

RNG: no algorithmic RNG is used by the lever. The benchmark mixed fixture remains seeded and is diagnostic only.

## Gates

- `cargo fmt -p fnx-classes -p fnx-python --check`
- `rch exec -- cargo check -p fnx-classes --all-targets`
- `rch exec -- cargo check -p fnx-python --all-targets --features pyo3/abi3-py310`
- `rch exec -- cargo clippy -p fnx-classes --all-targets -- -D warnings`
- `rch exec -- cargo clippy -p fnx-python --all-targets --features pyo3/abi3-py310 -- -D warnings` (RCH local fail-open due worker pressure)
- `rch exec -- maturin develop --release --features pyo3/abi3-py310`
- `pytest -q tests/python/test_graph_add_remove_kwarg_parity.py tests/python/test_multi_keyed_edges_set_algebra_parity.py tests/python/test_multidigraph_clear_edges.py` -> `50 passed`
- `git diff --check`
- `ubs crates/fnx-classes/src/digraph.rs crates/fnx-python/src/digraph.rs` -> exit `0`, critical `0`
- Selected UBS including the focused pytest file returned exit `1` because UBS flags existing pytest `assert` statements as security-sensitive criticals; no source criticals were reported.

## Score

Impact `2.6` x Confidence `4.0` / Effort `2.0` = `5.2`. Kept.

Next primitive: a batch-local attribute/log substrate for the attr and mixed MultiGraph/MultiDiGraph residuals. The remaining profile still points at add-edge boundary overhead, but the next attack should remove repeated per-edge attr materialization and duplicate-update churn rather than extend this fresh-keyed no-attr branch.
