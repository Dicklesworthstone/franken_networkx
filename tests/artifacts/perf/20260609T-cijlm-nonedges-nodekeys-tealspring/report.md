# br-r37-c1-cijlm pass 33: directed non_edges node-key reuse

## Target

Profile-backed residual after directed `_native_node_keys`: `non_edges(DiGraph)`
still re-entered `non_neighbors` once per source node, rebuilding the all-node
set and rediscovering the raw-neighbor path for every row.

## Lever

For directed graphs with `_native_node_keys`, `non_edges` now builds the all-node
set once and inlines the existing native-key/non-neighbor set difference per
source node. Generic graph objects fall back to the old `non_neighbors` loop.

## Baseline

- Release extension: `rch exec -- maturin develop --release --features pyo3/abi3-py310`
- Direct DiGraph `fnx.non_edges`: `0.1224300989s`
- Direct DiGraph NetworkX `non_edges`: `0.0788737959s`
- Hyperfine FNX command mean: `425.9 ms +/- 28.0 ms`
- Hyperfine NetworkX command mean: `411.9 ms +/- 21.6 ms`
- cProfile: `non_edges` `0.135s`, `non_neighbors` `0.041s`

## After

- Direct DiGraph `fnx.non_edges`: `0.0743535201s` (`1.65x` faster than baseline)
- Direct DiGraph NetworkX `non_edges`: `0.0840024910s`
- Hyperfine FNX command mean: `374.4 ms +/- 27.7 ms` (`1.14x` faster than baseline)
- Hyperfine NetworkX command mean: `371.4 ms +/- 17.8 ms`
- Direct MultiDiGraph after: FNX `0.0797285630s`, NetworkX `0.0761600911s`
- cProfile: `non_edges` `0.109s`; repeated `non_neighbors` dropped out of the hot list

## Isomorphism Proof

- Ordering preserved: exact ordered `list(non_edges(...))` and `list(non_neighbors(...))` compared to NetworkX for Graph, DiGraph, MultiGraph, and MultiDiGraph.
- Tie-breaking unchanged: CPython set-difference output was checked by exact output lists.
- Floating-point: N/A.
- RNG: N/A.
- Golden payload SHA: `e30552107fd61e18fa0b9fa080650b7799b068e99181390fdac7d33d4f9b0123` unchanged.

## Gates

- `python3 -m py_compile python/franken_networkx/__init__.py .../harness_cijlm_pass33.py`: pass
- Focused pytest: `27 passed, 649 deselected`
- `git diff --check` on touched files: pass
- `ubs` on harness: pass, 0 critical/warning
- `rch exec -- cargo check -p fnx-python --all-targets --features pyo3/abi3-py310`: pass on `vmi1227854`
- `cargo fmt -p fnx-python --check`: blocked by existing dirty Rust hunk in `crates/fnx-python/src/lib.rs`
- `rch exec -- cargo clippy -p fnx-python ...`: blocked by existing dirty `fnx-algorithms` `collapsible_if`
- `timeout 180 ubs python/franken_networkx/__init__.py`: timed out with no findings emitted

## Score

Impact `3`, confidence `4`, effort `1.5` -> Score `8.0`. Kept.
