# br-r37-c1-tgwv4 native weighted all_pairs_dijkstra

## Target

Profile-backed residual from
`tests/artifacts/perf/20260605T-all-pairs-dijkstra-weighted-pass5/report.md`:
after Dijkstra snapshot caching, `_fnx_to_nx` conversion was gone and the
remaining hot path was NetworkX `weighted.py:_dijkstra_multisource`.

Fresh baseline on `ef127f4b1` via rch:

- Hyperfine public FNX: 7.595382150311 s mean, 7.559578408740 s median.
- Hyperfine NetworkX: 8.277558373169 s mean, 8.146088566740 s median.
- Same-process public FNX float n80: 0.012365820443 s mean.
- Same-process NetworkX float n80: 0.010156475907 s mean.
- Same-process raw native float n80: 0.024102319103 s mean.
- Baseline golden SHA: `056c226e0486dea0dad0785536522592a7a38be2a8f5be517b45f3e7c098d28c`.

## One Lever

Replace the simple-graph raw `_fnx.all_pairs_dijkstra` implementation with a
packed-adjacency PyO3 Dijkstra path that:

- syncs Python-visible attrs into Rust before reading weights;
- precomputes `(neighbor_index, weight)` adjacency once;
- runs strict NetworkX-style Dijkstra relaxations over indices;
- emits Python dicts/lists directly instead of building a large Rust
  `Vec<(String, Vec<String>)>` result first;
- preserves Python `int` distance type for source zero and all-integer weights.

The public wrapper routes only safe no-cutoff simple `Graph`/`DiGraph` calls
with finite nonnegative string weights to this native path. Callable,
non-string, negative, nonnumeric, nonfinite, multigraph, and cutoff cases keep
the previous delegation/per-source behavior.

## Behavior Proof

Ordering and tie-breaking:

- Outer source order is `G.nodes()` / canonical insertion order.
- Inner distance/path dict order is Dijkstra finalize order from a FIFO
  sequence-number heap, matching NetworkX `heapq` `(distance, count, node)`.
- The existing stable `_reorder_by_distance` wrapper pass remains, so equal
  distances preserve the native finalize order.

Floating point:

- Relaxation uses strict `<`, matching NetworkX `_dijkstra_multisource`.
- Nonfinite, nonnumeric, and negative weights are still delegated before this
  native path is selected.

Distance types:

- Source distance is emitted as Python `0`, matching NetworkX.
- If every present edge weight is an integer AttrMap value, integer-valued
  distances are emitted as Python `int`.
- Float-weight distances remain Python `float`.

Mutation:

- Raw binding now calls `sync_rust_attrs_if_available` before packed adjacency
  construction.
- Golden proof includes a cached public call followed by
  `G[0][2]["weight"] = 1.0`; public and raw native digests match NetworkX.

RNG:

- No random state is read or written.

Golden SHA after:

- `af02673e0fad805fcf28fdf650b5ea19574e6ed9512c42f54b1341641c4d69a8`

All after golden cases matched NetworkX by value and digest:

- float `Graph`
- integer `Graph`
- float `DiGraph`
- post-mutation float `Graph`

## After Benchmark

After hyperfine via rch:

- FNX: 6.955712447291 s mean, 6.978484768720 s median.
- NetworkX: 8.540722281149 s mean, 8.051246209720 s median.
- FNX process speedup vs baseline: 1.0920x mean.
- FNX process relation after: 1.2279x faster than NetworkX.

Same-process float n80:

- Public FNX before: 0.012365820443 s mean.
- Public FNX after: 0.004892865228 s mean.
- NetworkX after: 0.010801342775 s mean.
- Public FNX speedup: 2.5274x.
- Public FNX relation after: 2.2098x faster than NetworkX.

Same-process integer n80:

- Public FNX before: 0.012979762338 s mean.
- Public FNX after: 0.004415323686 s mean.
- NetworkX after: 0.009750148223 s mean.
- Public FNX speedup: 2.9386x.
- Public FNX relation after: 2.2082x faster than NetworkX.

cProfile via rch:

- Baseline `case_all_pairs_dijkstra`: 3.039 s cumulative over 120 repeats.
- After `case_all_pairs_dijkstra`: 0.630 s cumulative over 120 repeats.
- After raw `_fnx.all_pairs_dijkstra`: 0.295 s cumulative over 120 repeats.
- NetworkX `_dijkstra_multisource` no longer appears in FNX profile.

Score: Impact 3 x Confidence 3 / Effort 2 = 4.5. Keep.

## Validation

- `rch exec -- cargo check -p fnx-python --all-targets --features pyo3/abi3-py310`: passed.
- `cargo fmt -p fnx-python --check`: passed.
- `rch exec -- cargo clippy -p fnx-python --all-targets --features pyo3/abi3-py310 -- -D warnings`: passed.
- `rch exec -- cargo test -p fnx-python python_algorithm_wrappers_preserve_mode --features pyo3/abi3-py310`: passed.
- `pytest tests/python/test_shortest_path.py tests/python/test_all_pairs_dijkstra_inner_order_parity.py tests/python/test_more_all_pairs_outer_order_parity.py tests/python/test_multigraph_algorithms.py -q`: 135 passed.
- `ubs --only=rust crates/fnx-python/src/algorithms.rs`: 0 critical; warnings are broad pre-existing inventory in the large file.

Validation gap:

- `ubs --only=python python/franken_networkx/__init__.py` exceeded several minutes on one file and was terminated; no result was produced.

## Reprofile

The Dijkstra residual shifted from NetworkX execution to local wrapper/output
post-processing:

- `_digest` / `_stable` dominates the benchmark process profile.
- The remaining FNX implementation cost is `_fnx.all_pairs_dijkstra` plus the
  Python wrapper's `_reorder_by_distance` pass.

Next primitive: eliminate the redundant Python `_reorder_by_distance` pass for
raw packed all-pairs outputs with a proof that raw finalization order is already
NetworkX order for default-unit and weighted simple graphs. Target ratio: at
least 1.10x on the same all_pairs_dijkstra_weighted profile case.

## Rebase Verification

After rebasing onto `origin/main` at `773bd466c`, reran the release extension
build and focused proof:

- `rebased_golden.jsonl`: same SHA
  `af02673e0fad805fcf28fdf650b5ea19574e6ed9512c42f54b1341641c4d69a8`; all
  cases still match NetworkX by value and digest.
- `rebased_same_process_float_n80.jsonl`: public FNX 0.004618021556 s mean,
  NetworkX 0.010809706673 s mean, FNX 2.3419x faster.
