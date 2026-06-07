# MultiGraph/MultiDiGraph Constructor Batch Kernel

- Bead: `br-r37-c1-04z53`
- Agent: `TealSpring`
- Date: `2026-06-07`
- Lever: guarded constructor-only batch path for list/tuple edge lists with exact `int` endpoints, exact `str` explicit keys, and optional dict attrs.
- Verdict: kept, Score `8.0`.

## Profile-Backed Target

The target came from Pass 12's rejected `MultiGraph` row-index flip, which showed the next useful primitive had to batch constructor endpoint/key work and native commit instead of partially changing persistent rows.

Baseline evidence in this bundle:

- Direct `MultiGraph` keyed ctor FNX/NX best ratio: `1.698x`
- Direct `MultiDiGraph` keyed ctor FNX/NX best ratio: `2.039x`
- cProfile total: `13.266s`
- cProfile constructor cumulative: `10.060s`
- Python validation cumulative: `0.185s`

That profile keeps the optimization target inside native constructor absorption, not wrapper validation.

## Behavior Proof

Golden proof SHA stayed unchanged:

- `baseline_proof.json`: `0cca4791c50613c0e42ab19376089edee5ebc441a657cc1263cedd28a209df2d`
- `after_proof.json`: `0cca4791c50613c0e42ab19376089edee5ebc441a657cc1263cedd28a209df2d`
- `final_proof.json`: `0cca4791c50613c0e42ab19376089edee5ebc441a657cc1263cedd28a209df2d`

Isomorphism surface covered node order, successor/predecessor/neighbor order, edge key order, duplicate explicit-key update order, graph attrs, edge attrs, self-loops, copy, pickle round-trip, and auto-key controls. `MultiGraph` numeric/bool display-conflict parity remains the known current mismatch and did not change; `MultiDiGraph` display-conflict parity remains true. No floating-point algorithm output was introduced. RNG is only fixture generation with a fixed seed.

Focused constructor parity:

- `rch exec -- .venv/bin/pytest tests/python/test_dicsr_cache_parity.py::test_ctor_bulk_absorb_parity tests/python/test_dicsr_cache_parity.py::test_digraph_ctor_bulk_absorb_and_get_edge_data_lazy tests/python/test_ctor_str_and_third_element_parity.py -q`
- Result: `19 passed`

## Benchmark Gate

Same-command hyperfine means:

| Scenario | Baseline | After | Speedup |
|---|---:|---:|---:|
| `MultiGraph` keyed ctor | `1.505543s` | `0.853205s` | `1.765x` |
| `MultiGraph` attr ctor | `1.072593s` | `0.842451s` | `1.273x` |
| `MultiGraph` mixed ctor | `1.278436s` | `1.115619s` | `1.146x` |
| `MultiDiGraph` keyed ctor | `1.665611s` | `0.915451s` | `1.819x` |
| `MultiDiGraph` attr ctor | `1.184658s` | `1.001739s` | `1.183x` |
| `MultiDiGraph` mixed ctor | `1.382933s` | `1.095805s` | `1.262x` |

Direct timing means:

| Scenario | Baseline FNX | After FNX | Speedup |
|---|---:|---:|---:|
| `MultiGraph` keyed ctor | `0.076541s` | `0.064039s` | `1.195x` |
| `MultiGraph` attr ctor | `0.080318s` | `0.073699s` | `1.090x` |
| `MultiGraph` mixed ctor | `0.133266s` | `0.127213s` | `1.048x` |
| `MultiDiGraph` keyed ctor | `0.105479s` | `0.087483s` | `1.206x` |

cProfile shifted:

- Total: `13.266s -> 10.281s`
- Constructor cumulative: `10.060s -> 7.339s`
- Python validation stayed small: `0.185s -> 0.168s`

## Gates

- rch `maturin develop --release --features pyo3/abi3-py310`: passed for baseline, after, and final source.
- rch `cargo check -p fnx-python --all-targets --features pyo3/abi3-py310`: passed.
- rch `cargo clippy -p fnx-python --all-targets --features pyo3/abi3-py310 -- -D warnings`: passed after converting two orphan doc comments to regular comments and acknowledging two `must_use` return values.
- `cargo fmt --check`: passed.
- `ubs crates/fnx-python/src/lib.rs crates/fnx-python/src/digraph.rs tests/artifacts/perf/20260607T-multigraph-ctor-batch-tealspring/multigraph_ctor_batch.py`: exit `0`; broad heuristic warnings only.

## Diagnosis

The batch path wins because it avoids the repeated `add_edge` constructor loop for the common exact-int/exact-string-key edge-list shape. It interns endpoints once, resolves public string keys with a batch-local pair map, creates Python edge-key/attr mirrors in order, and commits the native multigraph rows/buckets through one keyed edge batch. All non-exact shapes fall through to the old path.

The remaining constructor gap is now more attr/mirror-heavy: after profile still spends `7.339s` cumulative in constructor work, and attr/mixed cases gain less than keyed. The next primitive should be an attribute substrate swing, not another key-loop micro-tune: a lazy ordered mirror-log or typed attr descriptor path that stores Rust attrs plus compact ordered Python key/value entries during construction and materializes graph-owned `PyDict`s only on observation or duplicate update.
