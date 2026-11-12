# br-r37-c1-p34di adjacency row mirror report

## Target

- Profile-backed hotspot: adjacency/neighbors row iteration returned Rust/Python wrapper iterators instead of CPython `dict_keyiterator`, leaving `list(G[hub])`, `list(G.adj[hub])`, and `list(G.neighbors(hub))` dominated by wrapper boundary work.
- Alien primitive: write-coherent materialized row mirror. Keep Rust as the algorithm store, but materialize exact Python row dicts on first observation and update them in Rust mutators.

## Lever

- Added `Graph` `adj_row_py` and `DiGraph` `succ_row_py` / `pred_row_py` mirrors.
- Python `AtlasView` and private-aware neighbor wrappers now prefer native row dicts for `adj`, `succ`, and `pred`.
- `AtlasView.__iter__` returns the mirrored row's CPython dict iterator, so active row iterators inherit NetworkX mutation invalidation.
- Batch add fast paths fall back to the per-edge path once a row mirror exists, preventing cached rows from drifting.
- Mutator update calls are lazy-guarded so construction does not pay row-cache update probes before a row has been observed.

## Behavior proof

- Targeted Graph proof changed from baseline FNX mismatch SHA `b6656d13db4f45c1177b3930f84e0db2befba0aeaefb3bc2e2ef290864f61d01` to NetworkX-matching SHA `9aed5a16341f91d7afc88587936d896228d841ea5b3ad9b33cd385ae71aa9238`.
- Final broad golden: `93493903223b584269077b00519ba9221f231858b83cacdf3a68cbae0c1b8872`.
- `tealspring_full_after_proof.json`: `matches_nx.graph=true`, `matches_nx.digraph=true`.
- Iterator types: Graph and DiGraph row iterators, successors, predecessors, and neighbors all report `dict_keyiterator`.
- Mutation parity: Graph and DiGraph row iterators raise `RuntimeError: dictionary changed size during iteration`, matching NetworkX.
- Floating point / hash-equal nodes: proof includes `12.0` / `12` and mixed `0` / `0.0` / `True` surfaces.
- RNG: no RNG in this surface.

## Benchmark

Direct profiled row harness, degree 20000, repeat 15:

- `getitem_row_list` mean `0.0028584805s -> 0.0006235639s` = `4.58x`; median `0.0030168820s -> 0.0001525891s` = `19.77x`.
- `adj_row_list` mean `0.0018035734s -> 0.0001684731s` = `10.71x`; median `0.0014543639s -> 0.0001678180s` = `8.67x`.
- `neighbors_list` mean `0.0014214279s -> 0.0001653031s` = `8.60x`; median `0.0014424110s -> 0.0001634291s` = `8.83x`.
- `row_items` mean `0.0248803907s -> 0.0212494227s` = `1.17x`.

Whole-command `rch hyperfine` includes graph construction and Python process startup:

- `getitem_row_list` mean `0.4125154104s -> 0.3511530397s` = `1.17x`.
- `adj_row_list` mean `0.4146593478s -> 0.3505489896s` = `1.18x`.
- `neighbors_list` mean `0.4377067154s -> 0.3564517484s` = `1.23x`.

Broad Graph/DiGraph direct harness:

- `graph:neighbors` mean `0.0428527537s -> 0.0333819845s` = `1.28x`.
- `graph:adj_row` mean `0.0410550635s -> 0.0313482377s` = `1.31x`.
- `graph:getitem_row` mean `0.0406658490s -> 0.0331007384s` = `1.23x`.
- `digraph:successors` mean `0.0430502134s -> 0.0299461925s` = `1.44x`.
- `digraph:adj_row` mean `0.0404610895s -> 0.0327496189s` = `1.24x`.
- Low-degree `pred` rows and full adjacency snapshots are documented non-target tradeoffs in `tealspring_full_after_bench.json`.

## Gates

- `rch exec -- cargo check -p fnx-python --all-targets --features pyo3/abi3-py310`: passed.
- `rch exec -- cargo clippy -p fnx-python --all-targets --features pyo3/abi3-py310 -- -D warnings`: passed.
- Fresh release install: `CARGO_TARGET_DIR=target-tealspring-adj-mirror rch exec -- maturin develop --release --features pyo3/abi3-py310`: passed.
- `cargo fmt -p fnx-python --check`: passed.
- `py_compile`: passed for `python/franken_networkx/__init__.py` and both harnesses.
- Focused pytest: `88 passed`.
- UBS selected Rust + harness files: exit `0`, no critical issues; warning inventory is pre-existing broad file-scope heuristics.
- UBS standalone `python/franken_networkx/__init__.py`: timed out at 120s with no findings emitted; covered by proof, py_compile, focused pytest, check, and clippy.

## Score

- Impact `4`: removes wrapper iteration from the profiled row hot path with 4.58x-10.71x direct mean wins and 1.17x-1.23x whole-command wins.
- Confidence `4`: NetworkX golden and focused tests pass; same-harness baseline/after and `rch` context recorded.
- Effort `2.5`: one coherent row-mirror lever across Graph/DiGraph view surfaces.
- Score `6.4`; keep.

## Next profile target

- Reprofile after landing. If adjacency row construction drops out, the next deeper primitive is MultiGraph/MultiDiGraph native row mirrors and attr-log materialization for residual row-items and constructor-heavy surfaces.
