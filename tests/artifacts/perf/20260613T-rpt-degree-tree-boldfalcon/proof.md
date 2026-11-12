# br-r37-c1-04z53.78 random_powerlaw_tree degree_sequence_tree batching

## Target

- Profile-backed fallback target: no ready `[perf]` beads were available from `br ready --json`.
- Routing sweep target: `random_powerlaw_tree(n=300, gamma=3, seed=5, tries=1000)`.
- Current-head routing result: FNX/NX digests matched, FNX median 0.002169584s vs NX median 0.000582902s, 3.722x slower.
- Focused baseline result in this bundle: FNX median 0.002229920996s vs NX median 0.000693943002s, 3.213x slower.

## One Lever

`degree_sequence_tree` already constructs the backbone path first, then appends leaf edges in nested `(source, target)` order. The old implementation crossed the graph boundary once per source:

```python
for source in range(1, backbone_nodes - 1):
    extra_edges = degrees.pop() - 2
    graph.add_edges_from((source, target) for target in range(last, last + extra_edges))
    last += extra_edges
```

The candidate accumulates the exact same edge tuples in a Python list, preserving the same source loop and target range order, then calls `graph.add_edges_from(leaf_edges)` once.

## Isomorphism Proof

- Node order: unchanged. `empty_graph`, the `[0]` special case, `add_path(graph, range(backbone_nodes))`, and all validation checks are untouched.
- Edge order: unchanged. The new `leaf_edges.extend((source, target) for target in range(last, last + extra_edges))` executes the same nested source/target iteration as the old per-source generator. The single `add_edges_from` receives the concatenation of the same per-source sequences.
- Tie-breaking: unchanged. No sorting, dict/set iteration, or comparator was added.
- RNG: unchanged. The optimization is after `random_powerlaw_tree_sequence`; it does not touch seed handling, `paretovariate`, retries, or validation.
- Floating point: unchanged. The edited function performs no floating-point arithmetic.
- Error behavior: unchanged for invalid sequences and directed graphs; all guards execute before the optimized block.

## Golden Output

- Baseline FNX SHA256: `9acb9600008103deee5400c8f4c3b8354aedf03072c9a4c936cdbaa024d92aec`
- Baseline NX SHA256: `9acb9600008103deee5400c8f4c3b8354aedf03072c9a4c936cdbaa024d92aec`
- Candidate FNX SHA256: `9acb9600008103deee5400c8f4c3b8354aedf03072c9a4c936cdbaa024d92aec`
- Candidate NX SHA256: `9acb9600008103deee5400c8f4c3b8354aedf03072c9a4c936cdbaa024d92aec`
- Golden artifact SHA256: `9467bfdb009f38e628da087d329e36c1429b2019a5b1664c26a303ca7514b51d` for both baseline and candidate golden JSON.

## Benchmark

Command family: `rch exec -- python3 random_powerlaw_tree_harness.py ...` through the single baseline/candidate shell bundles in this directory. RCH warned that Python benchmarking is a non-compilation command; this is intentional because the hot path is Python-level graph construction over the same `rch`-built extension.

| Impl | Median seconds |
| --- | ---: |
| Baseline FNX | 0.002229920996 |
| Candidate FNX | 0.001048495003 |
| Baseline NX | 0.000693943002 |
| Candidate NX | 0.000620483988 |

- Same-case FNX speedup: 2.126783x.
- Baseline FNX/NX: 3.213407x slower.
- Candidate FNX/NX: 1.689802x slower.

## Profile Delta

- Baseline profile: 136 calls to `add_edges_from`, 136 calls to `_try_add_edges_from_batch`.
- Candidate profile: 1 call to `add_edges_from`, 1 call to `_try_add_edges_from_batch`.

## Score

- Impact: 2.126783x.
- Confidence: 4.0, because golden SHA, first/last edge order, and focused profile mechanism match.
- Effort: 1.0.
- Score: 8.507, keep.

## Verification

- `python3 -m py_compile python/franken_networkx/__init__.py tests/artifacts/perf/20260613T-rpt-degree-tree-boldfalcon/random_powerlaw_tree_harness.py`: passed.
- Focused pytest through `rch exec -- python3 -m pytest ...`: passed, `4 passed in 0.42s`.
- `rch exec -- cargo check -p fnx-python --lib`: passed on `vmi1153651`; only pre-existing `fnx-generators` `unused_must_use` warnings were emitted.
- `rch exec -- cargo fmt -p fnx-python --check`: failed on pre-existing Rust formatting drift in `crates/fnx-python/src/algorithms.rs`, `digraph.rs`, `lib.rs`, and `readwrite.rs`. No Rust files were edited for this bead.
- `rch exec -- cargo clippy -p fnx-python --lib -- -D warnings`: failed on pre-existing `fnx-generators` `unused_must_use` errors at `crates/fnx-generators/src/lib.rs:538`, `621`, `666`, `6218`, and `6758`. No Rust files were edited for this bead.
- `timeout 90s ubs python/franken_networkx/__init__.py .skill-loop-progress.md tests/artifacts/perf/20260613T-rpt-degree-tree-boldfalcon/random_powerlaw_tree_harness.py tests/artifacts/perf/20260613T-rpt-degree-tree-boldfalcon/proof.md`: timed out during Python scan and produced no finding before timeout.

## Alien-Graveyard Mapping

The applied primitive is boundary batching for graph construction: accumulate a cache-local edge batch in deterministic iteration order and emit one graph-kernel call instead of many small boundary calls. This matches the graveyard recommendation to harvest batched graph-kernel style primitives while preserving explicit graph-regime proof artifacts.
