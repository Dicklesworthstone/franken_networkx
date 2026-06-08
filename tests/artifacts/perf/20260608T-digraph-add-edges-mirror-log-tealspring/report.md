# DiGraph Add Edges Dead Row-Staging Removal

Bead: `br-r37-c1-jyibx`
Baseline source: `9d41e81a9`
Agent: `TealSpring`

## Profile-backed target

The current-tip baseline still shows attributed `DiGraph.add_edges_from` as a real residual:

- Direct `method_attr`: FNX best `0.0095782482996583s`, NetworkX best `0.003702227200847119s`, ratio `2.5871584265456935x`.
- Hyperfine timing payload: median ratio `2.6328410217621974x`, FNX median `0.009186521987430751s`, NetworkX median `0.003489204973448068s`.
- cProfile over 200 FNX builds: `_try_add_edges_from_batch` `1.633s` of `1.649s` total.

## Lever

One lever only: remove the unused `successor_rows` and `predecessor_rows` `IndexMap` staging tables inside `DiGraph::extend_prepared_edges_with_attrs_row_staged_unrecorded`.

Those maps were allocated and populated for every inserted edge, cloning endpoint strings and probing row maps, but were never read. The real edge insertion, successor index push, predecessor index push, duplicate merge, revision bump, and edge-order behavior remain unchanged.

## Benchmark

Focused direct `method_attr`:

- FNX best `0.0095782482996583s -> 0.007726342102978378s` (`1.239687x`)
- FNX median `0.01131257259985432s -> 0.008497594099026173s` (`1.331268x`)
- FNX mean `0.010908164745861931s -> 0.008455827542846756s` (`1.290017x`)
- vs-NetworkX best ratio `2.5871584265456935x -> 2.3023591763837565x`

RCH-wrapped hyperfine process envelope:

- mean `0.7143843996950001s -> 0.6811046180650001s` (`1.048883x`)
- median `0.7186551158200001s -> 0.6731771119400001s`

cProfile:

- total `1.649s -> 1.405s`
- native `_try_add_edges_from_batch` `1.633s -> 1.385s`

## Isomorphism proof

Golden SHA before and after:

`0ef891991ff0d949b8dd9eedc481a1b18e6b11952777dbba85080dbf1f40bdf8`

The removed staging maps had no readers. Edge stream order, node order, successor and predecessor row order, duplicate merge order, attr dict order, live edge-data dict identity, tie-breaking, floating-point values, and seeded RNG fixtures are unchanged by construction and verified by the proof harness plus focused parity tests.

## Gates

- `cargo fmt -p fnx-classes --check`
- `rch exec -- cargo check -p fnx-classes --all-targets`
- `rch exec -- cargo clippy -p fnx-classes --all-targets -- -D warnings`
- `rch exec -- maturin develop --release --features pyo3/abi3-py310`
- `pytest -q tests/python/test_add_edges_attr_batch_parity.py` -> `15 passed`
- `git diff --check`
- `ubs crates/fnx-classes/src/digraph.rs` -> exit `0`, critical `0`

## Score

Impact `2.4` x Confidence `4.0` / Effort `1.0` = `9.6`. Kept.

Next primitive: implement the actual row-local indexed staging arena that the removed dead maps were meant to become. Carry source and target node indices through the batch descriptor so the inner commit does not repeatedly resolve `(source, target)` strings to node indices, while preserving global edge order and duplicate merge semantics.
