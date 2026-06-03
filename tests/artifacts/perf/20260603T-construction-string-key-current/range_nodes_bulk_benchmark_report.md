# Range Node Bulk Construction Benchmark Report

## Target

- Bead: `br-r37-c1-w1dm8`
- Profile-backed hotspot: `Graph.add_nodes_from(range(100_000))`.
- Original direct sweep baseline: FNX `0.30639516528546146s`, NetworkX `0.05005896399546016s`, ratio `6.120685304499078x`.
- Original cProfile baseline: `2.882s` total over five `add_nodes_int` builds, with `2.326s` in Python `add_nodes_from`, `1.941s` in the per-node wrapper, and `1.577s` in `Graph.add_node`.
- Original hyperfine process envelope: `1.503s +/- 0.097s`.

## Lever

One production lever was kept:

- Add `Graph::extend_nodes_unrecorded` in `fnx-classes` for batched exact node insertion with one compatibility evidence record.
- Add a `Graph._fast_add_int_nodes_range_stop(stop)` PyO3 method for the exact `range(0, stop, 1)` no-attrs construction path.
- Route only exact Python `Graph.add_nodes_from(range(...))` with no attrs and no subclass through the native range method.

Rejected or non-kept sublevers from the same bead remain documented separately:

- `edge_key_lookup_string` PyString downcast failed the keep gate.
- Wrapper-only range dispatch without the inner bulk insertion did not materially improve the target.

## Final-Source Results

Direct final sweep (`after_range_nodes_bulk_final_sweep.jsonl`):

- `add_nodes_int`: FNX `0.30639516528546146s -> 0.08562762743427552s` mean, `3.58x` faster.
- `add_nodes_int`: FNX median `0.28989488701336086s -> 0.08426945400424302s`, `3.44x` faster.
- FNX-vs-NetworkX ratio moved `6.120685304499078x -> 2.5469851363781895x`.
- Golden digest stayed `eae2ed4eadc93d3264aef2fb5cd05bce54b2c934b5805383f8e5ad4113505b75`; `digests_match=true`.

Focused final target run (`after_add_nodes_int_bulk_final.jsonl`):

- FNX `0.30639516528546146s -> 0.1052997077100112s` mean, `2.91x` faster.
- FNX median `0.28989488701336086s -> 0.09938310401048511s`, `2.92x` faster.
- FNX-vs-NetworkX ratio moved `6.120685304499078x -> 3.02791308573964x`.
- Golden digest stayed `eae2ed4eadc93d3264aef2fb5cd05bce54b2c934b5805383f8e5ad4113505b75`; `digests_match=true`.

cProfile final-source comparison:

- Total profiled build time: `2.882s -> 0.486s`, `5.93x` faster.
- Python `add_nodes_from` section: `2.326s -> 0.313s`, `7.43x` faster.
- The per-node Python wrapper path disappears from the target; final profile spends `0.311s` over five calls in `_fast_add_int_nodes_range_stop`.

Hyperfine final-source process envelope:

- `1.503s +/- 0.097s -> 559.8ms +/- 37.0ms`, `2.69x` faster.
- Command: `RCH_ENV_ALLOWLIST=PYTHONPATH rch exec -- env PYTHONPATH=python .venv/bin/python tests/artifacts/perf/20260603T-construction-string-key-current/bench_construction.py bench --case add_nodes_int --impl fnx --repeats 3`.

Residual construction sweep after this lever:

- `plain_edges_int`: ratio `2.025176159202857x`, digest matched.
- `multigraph_int_keys`: ratio `4.6938179667281235x`, digest matched.
- `multigraph_str_keys`: ratio `4.485727950204022x`, digest matched.

Those residuals are the next profile-backed construction targets; they require the deeper integer-interning / contiguous-ID memory-layout primitive rather than more string-helper tuning.

## Score

- Impact: `5` (direct and hyperfine target both exceed `2x`; cProfile target exceeds `5x`).
- Confidence: `4` (multiple final-source rch/hyperfine runs, golden SHA unchanged, focused parity tests passed).
- Effort: `2` (bounded exact-Graph range path plus one small `fnx-classes` batch primitive).
- Score: `5 * 4 / 2 = 10.0`.

Decision: keep.
