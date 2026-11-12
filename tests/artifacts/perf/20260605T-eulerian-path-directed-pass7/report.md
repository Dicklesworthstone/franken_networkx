# br-r37-c1-04z53.54 pass 7 report

## Target

- Profile-backed bead: `[perf][no-gaps] Native eulerian_path directed residual`.
- Baseline target came from `tests/artifacts/perf/20260604T-post-chain-residual-sweep/delegation_sweep.jsonl`, where `eulerian_path_directed` remained a profiled FNX/NX residual.
- One lever only: reuse `DiGraph`'s existing node index during directed reverse-adjacency construction instead of building a temporary `HashMap<&str, usize>` for every call.

## Benchmark

Command family:

```text
/data/projects/franken_networkx/.venv/bin/python tests/artifacts/perf/20260604T-delegation-goldmine-sweep/bench_delegation_goldmines.py --case eulerian_path_directed --impl {fnx,nx} --repeats 30
```

| Run | Impl | Mean | Median | Stddev |
| --- | --- | ---: | ---: | ---: |
| Baseline | FNX | 0.51488711862s | 0.46021691342s | 0.15724141718s |
| Baseline | NX | 0.85011220462s | 0.85116611342s | 0.01390653480s |
| After | FNX | 0.39959846626s | 0.39517798206s | 0.02340008595s |
| After | NX | 0.84325570106s | 0.83983242256s | 0.02776639074s |
| After 20-run confirm | FNX | 0.45079298399s | 0.42851972044s | 0.06552844306s |
| After 20-run confirm | NX | 0.96525723104s | 0.94447587444s | 0.08766062678s |

Primary same-worker delta: FNX mean improved 0.51488711862s -> 0.39959846626s, a 22.39% reduction. Median improved 0.46021691342s -> 0.39517798206s, a 14.13% reduction. FNX/NX moved from 1.65x faster to 2.11x faster on the primary after run, with a 2.14x faster confirmation run.

Score: Impact 3 x Confidence 4 / Effort 1 = 12.0, so this clears the keep gate.

## Isomorphism proof

- Ordering: the loop still iterates `digraph.edges_ordered_borrowed()` in the same order and pushes to `reverse_adj` in that same order. Hierholzer traversal still consumes `edge_pos[current]` monotonically from zero, so edge tie-break order is unchanged.
- Start selection: `directed_reverse_eulerian_start` is unchanged. The start vertex index is now read from `digraph.get_node_index(start)` instead of a freshly built map over `nodes_ordered()`. Both maps represent the same stable node order for nodes already present in the graph.
- Tie-breaking: no branch deciding between candidate edges changed. The only changed operation is the source of node-id-to-index lookup.
- Floating point: no floating-point operations in this code path.
- RNG: no random state or seed use in this code path.
- Error behavior: all sources and targets come from the same `DiGraph` edge iterator, and `start` comes from the existing Eulerian start validation. For a valid internal graph, `get_node_index` returns the same index as the temporary map. If graph storage were internally inconsistent, the function still returns `None` through the existing `Option` contract instead of panicking.

## Golden output

- Baseline artifact sha256: `ec9932a5d9e6220b722c7b0d96f899b84f2876e6e249853ad8aa169725880ecb`.
- After artifact sha256: `425a4df147e712e88fa8622bbbdab45f6fe8803a1adc908fda624c0a14f0e4d2`.
- `after_golden.jsonl` records `equal: true` and `typed_sha_equal: true` for:
  - `directed_path_2000`
  - `directed_branch_circuit`
  - `directed_cycle_source`

## Verification

- `rch exec -- cargo check -p fnx-algorithms`: pass.
- `cargo fmt -p fnx-algorithms` and `cargo fmt --check -p fnx-algorithms`: pass.
- `rch exec -- cargo clippy -p fnx-algorithms -- -D warnings`: pass.
- `rch exec -- cargo test -p fnx-algorithms eulerian_path_directed -- --nocapture`: pass, 4 directed Eulerian tests.
- Python focused parity: `276 passed in 0.66s` for `tests/python/test_eulerian_path_directed_parity.py tests/python/test_eulerian_conformance.py`.
- UBS was run on `crates/fnx-algorithms/src/lib.rs` and returned 1 due a pre-existing heuristic at `crates/fnx-algorithms/src/lib.rs:32303`, identical at `HEAD` and outside this diff.

## Post-profile note

After this lever, the next deeper primitive to attack is a cache-local directed edge-index adjacency for Eulerian traversal so repeated calls do not rebuild reverse adjacency from borrowed edge tuples. Target ratio: another 1.2x to 1.5x on the same directed residual, with ordering preserved by storing edge-order indices directly.
