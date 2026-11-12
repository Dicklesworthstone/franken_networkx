# br-r37-c1-04z53.9003 Graph plain int edge batch

Target: profile-backed `Graph.add_edges_from([(0, 1), ...])` fresh exact-int prefix edge batch.

Profile basis:
- `plain_edges_int_profile.txt`: fresh construction sweep residual put 0.405s/0.471s in `Graph._try_add_edges_from_batch`.
- `graph_plain_baseline_profile.txt`: focused 5x 50k unique path spent 0.532s in `_try_add_edges_from_batch`.

Lever:
- Add a fresh-graph exact-`int` contiguous-prefix fast path before the existing general plain-edge batch.
- Validate all inputs before mutation and fall back unchanged for bools, negatives, non-prefix first-seen order, non-tuples, attributed edges, existing graphs, or short batches.
- Materialize nodes via the established lazy int-node range path, then add edges in existing index space.

Behavior proof:
- `graph_plain_baseline_golden.json` bundle SHA: `38381ddccfed255858247b8d9be93c79b151c8bd9407955de00dd0d4a4dd3538`
- `graph_plain_candidate_golden.json` bundle SHA: `38381ddccfed255858247b8d9be93c79b151c8bd9407955de00dd0d4a4dd3538`
- Golden cases: `unique_path`, `duplicate_edges`, `self_loops`, `non_prefix_order`, `bool_endpoint`, `negative_endpoint`, `tuple_input`, `existing_graph`.
- Exact comparison surface: node order, `edges(data=True)` order, Python type/repr payloads, duplicate/self-loop semantics.
- Floating point and RNG: not used by this deterministic construction path.

Timing:
- Direct FNX median: 0.07951162799145095s -> 0.021813243016367778s, 3.65x faster.
- Direct FNX mean: 0.08386983909506605s -> 0.025882113095245917s, 3.24x faster.
- Hyperfine FNX mean: 0.5929923078200001s -> 0.5237915868s, 1.13x faster.
- Profiled `_try_add_edges_from_batch`: 0.532s -> 0.092s across five 50k-edge builds.

Gate results:
- `cargo check -p fnx-python --lib` via rch: pass; existing warnings only.
- Selected Python parity via rch: 49 passed.
- `ubs crates/fnx-python/src/lib.rs tests/artifacts/perf/20260614T-next-routing-codex/bench_graph_plain_int_edges.py`: no critical findings; remaining warnings are existing broad inventory from `lib.rs`.
- `git diff --check`: pass.
- `cargo fmt --check --all`: blocked by pre-existing formatting drift in unrelated workspace files.

Score:
- Impact 4, Confidence 4, Effort 2 => 8.0. Keep.
