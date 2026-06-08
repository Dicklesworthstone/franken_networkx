# br-r37-c1-p34di adjacency row mirror report

## Target

- Profile-backed hotspot: adjacency/neighbors row iteration returned Rust/Python wrapper iterators instead of CPython `dict_keyiterator`, leaving `list(G[hub])`, `list(G.adj[hub])`, and `list(G.neighbors(hub))` dominated by wrapper boundary work.
- Alien primitive: write-coherent materialized row mirror. Keep Rust as the algorithm store, but materialize exact Python row dicts on first observation and update them in Rust mutators.

## Lever

- Added `Graph` `adj_row_py` and `DiGraph` `succ_row_py` / `pred_row_py` mirrors.
- Python `AtlasView` and private-aware neighbor wrappers now prefer native row dicts for `adj`, `succ`, and `pred`.
- `DiAtlasView.__iter__` returns the mirrored row's CPython dict iterator, so active row iterators inherit NetworkX mutation invalidation.
- Batch add fast paths fall back to the per-edge path once a row mirror exists, preventing cached rows from drifting.

## Behavior proof

- Final broad golden: `93493903223b584269077b00519ba9221f231858b83cacdf3a68cbae0c1b8872`.
- `final_proof.json`: `matches_nx.graph=true`, `matches_nx.digraph=true`.
- Iterator types: Graph and DiGraph row iterators, successors, predecessors, and neighbors all report `dict_keyiterator`.
- Mutation parity: Graph and DiGraph row iterators raise `RuntimeError: dictionary changed size during iteration`, matching NetworkX.
- Floating point / hash-equal nodes: proof includes `12.0` / `12` and mixed `0` / `0.0` / `True` surfaces.
- RNG: no RNG in this surface.

## Benchmark

Direct profiled row harness, degree 20000, repeat 15:

- `getitem_row_list` median `0.0015311220s -> 0.0001006811s` = `15.21x`.
- `adj_row_list` median `0.0015276449s -> 0.0001042370s` = `14.66x`.
- `neighbors_list` median `0.0021210189s -> 0.0001034361s` = `20.51x`.
- `row_items` median `0.0304933300s -> 0.0217248879s` = `1.40x`.

Whole-command `rch hyperfine` includes graph construction and Python process startup:

- `graph:getitem_row` mean `0.3403115266s -> 0.3248727364s` = `1.05x`.
- `digraph:successors` mean `0.3494535795s -> 0.3251583815s` = `1.07x`.
- `digraph:adj_row` mean `0.3420849323s -> 0.3281997844s` = `1.04x`.
- Construction-heavy `graph:neighbors` and `graph:adj_row` whole-command means were flat/slightly slower (`0.98x`, `0.99x`), while the profiled row target shows the real win.

## Gates

- `rch exec -- cargo check -p fnx-python --all-targets --features pyo3/abi3-py310`: passed.
- `rch exec -- maturin develop --release --features pyo3/abi3-py310`: passed.
- `rch exec -- cargo clippy -p fnx-python --all-targets --features pyo3/abi3-py310 -- -D warnings`: passed.
- `cargo fmt --check`: passed.
- `git diff --check`: passed.
- Focused pytest: `4 passed`.
- UBS Rust selected files: no critical findings; warning inventory is pre-existing broad file-scope heuristics.
- UBS small Python harnesses: no critical/warning findings after trusted local pickle-roundtrip annotation.

## Score

- Impact `5`: removes wrapper iteration from the profiled row hot path with 14.66x-20.51x direct wins.
- Confidence `4`: NetworkX golden and focused tests pass; same-harness baseline/after and `rch` context recorded.
- Effort `2`: one coherent row-mirror lever across Graph/DiGraph view surfaces.
- Score `10.0`; keep.

## Next profile target

- Reprofile after landing. If adjacency row construction drops out, the next deeper primitive is MultiGraph/MultiDiGraph native row mirrors and attr-log materialization for residual row-items and constructor-heavy surfaces.
