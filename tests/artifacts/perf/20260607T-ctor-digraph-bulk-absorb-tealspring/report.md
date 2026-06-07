# DiGraph Generator Constructor Bulk Absorb Proof

Bead: `br-r37-c1-d58s8`

Source lever: landed concurrently as `2078e8e56` (`perf(ctor): DiGraph bulk absorb (directed twin) + get_edge_data lazy-mirror fix`) and refreshed after the lazy edge-data reader fix in this follow-up.

This bundle is supplemental proof and re-benchmark evidence for the directed constructor bulk-absorb lever. Baseline was measured from scratch worktree `/data/projects/.scratch/fnx-digraph-ctor-baseline-20260607-0349` at `511637095`; after was refreshed from the live repo after the lazy edge-data reader fix and clippy-clean validation pass.

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
| generator_plain, 6000 edges | 17.61 ms | 8.53 ms | 2.06x | 3.88x | 1.98x |
| generator_attr, 6000 edges | 31.44 ms | 15.73 ms | 2.00x | 5.95x | 3.42x |

Paired `hyperfine` via `rch exec`:

| Scenario | Baseline Mean | After Mean | Speedup |
| --- | ---: | ---: | ---: |
| `fnx-loop-plain --loops 40` | 1.273 s | 0.696 s | 1.83x |
| `fnx-loop-attr --loops 30` | 1.299 s | 0.840 s | 1.55x |

`cProfile` native constructor loop:

| Metric | Baseline | After | Speedup |
| --- | ---: | ---: | ---: |
| Total profile wall | 4.407 s | 2.310 s | 1.91x |
| `build_ctor` cumulative | 4.369 s | 2.276 s | 1.92x |

## Validation

- Focused Python parity after rebuild: `34 passed`
  - `tests/python/test_dicsr_cache_parity.py::test_digraph_ctor_bulk_absorb_and_get_edge_data_lazy`
  - `tests/python/test_dicsr_cache_parity.py::test_cache_invalidation_through_mutations`
  - `tests/python/test_graph_add_remove_kwarg_parity.py`
- Touched-crate format gate: `cargo fmt -p fnx-algorithms -p fnx-classes -p fnx-python --check` passed.
- Crate-scoped build gate via rch: `cargo check -p fnx-python --all-targets --features pyo3/abi3-py310` passed.
- Crate-scoped lint gate via rch: `cargo clippy -p fnx-python --all-targets --features pyo3/abi3-py310 -- -D warnings` passed.
- Focused Rust invariant: `cargo test -p fnx-classes remove_nodes_from_matches_repeated_removal_and_rebuilds_indices` passed. `rch` fell open locally because no worker had admissible slots.

## Score

Impact `4` x Confidence `4` / Effort `2` = `8.0`.

Verdict: keep. The lever clears the Score >= 2.0 gate and shifts the residual toward DiGraph `add_edges_from` wiring, Multi twins, P2(c), and union/compose recheck as recorded on `br-r37-c1-d58s8`.
