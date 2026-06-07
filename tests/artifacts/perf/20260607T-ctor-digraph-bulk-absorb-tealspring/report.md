# DiGraph Generator Constructor Bulk Absorb Proof

Bead: `br-r37-c1-d58s8`

Source lever: landed concurrently as `2078e8e56` (`perf(ctor): DiGraph bulk absorb (directed twin) + get_edge_data lazy-mirror fix`).

This bundle is supplemental proof and re-benchmark evidence for the directed constructor bulk-absorb lever. Baseline was measured from scratch worktree `/data/projects/.scratch/fnx-digraph-ctor-baseline-20260607-0349` at `511637095`; after was measured from the live repo after the landed directed constructor commit.

## Proof

- Golden SHA: `64f1bd81e2a0a63d98950806501fb3fdb33048f0b7adc1ea2e3d994637bbbfb1`
- Baseline proof: `baseline_proof.json`
- After proof: `after_proof.json`
- Cases: 6 directed constructor cases, including duplicate directed edges, graph kwargs, generator input, existing pre-lever malformed tuple behavior, and live empty `edges(data=True)` attr dict mutation.
- Ordering/tie-break: node order, edge order, `succ` order, and `pred` order are included in the canonical proof blob.
- FP/RNG: no floating-point algorithm output is involved; random fixture generation is seeded and stable.
- Verdict: after proof SHA equals baseline proof SHA, so observable behavior for this proof surface is unchanged.

## Benchmarks

Direct Python timing, best per constructor call:

| Scenario | Baseline | After | Speedup | FNX/NX Baseline | FNX/NX After |
| --- | ---: | ---: | ---: | ---: | ---: |
| generator_plain, 6000 edges | 17.61 ms | 13.60 ms | 1.29x | 3.88x | 3.01x |
| generator_attr, 6000 edges | 31.44 ms | 18.93 ms | 1.66x | 5.95x | 3.71x |

Paired `hyperfine` via `rch exec`:

| Scenario | Baseline Mean | After Mean | Speedup |
| --- | ---: | ---: | ---: |
| `fnx-loop-plain --loops 40` | 1.342 s | 0.985 s | 1.36x |
| `fnx-loop-attr --loops 30` | 1.665 s | 1.018 s | 1.64x |

`cProfile` native constructor loop:

| Metric | Baseline | After | Speedup |
| --- | ---: | ---: | ---: |
| Total profile wall | 4.407 s | 3.299 s | 1.34x |
| `build_ctor` cumulative | 4.369 s | 3.256 s | 1.34x |

## Validation

- Focused Python parity after rebuild: `37 passed`
  - `tests/python/test_dicsr_cache_parity.py`
  - `tests/python/test_cross_class_ctor_parity.py`
  - `tests/python/test_from_nx_graph_adj_order_parity.py`
- Touched-file format gate: `rustfmt --edition 2024 --check crates/fnx-python/src/digraph.rs` passed.
- Crate-scoped build gate via rch: `cargo check -p fnx-python --all-targets --features pyo3/abi3-py310` passed.
- Known out-of-scope gate blockers:
  - `cargo clippy -p fnx-python --all-targets --features pyo3/abi3-py310 -- -D warnings` failed on pre-existing `clippy::type_complexity` in `crates/fnx-classes/src/digraph.rs:129`.
  - Workspace `cargo fmt --check` failed due existing formatting drift across unrelated files.

## Score

Impact `4` x Confidence `4` / Effort `2` = `8.0`.

Verdict: keep. The lever clears the Score >= 2.0 gate and shifts the residual toward DiGraph `add_edges_from` wiring, Multi twins, P2(c), and union/compose recheck as recorded on `br-r37-c1-d58s8`.
