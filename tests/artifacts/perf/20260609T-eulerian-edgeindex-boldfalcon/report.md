# br-r37-c1-04z53 fallback pass: eulerian edge-index reverse adjacency

## Target

- Profile-backed residual: `eulerian_path_directed` remained in the post-native Eulerian hot path after the earlier `get_node_index` pass.
- Prior report: `tests/artifacts/perf/20260605T-eulerian-path-directed-pass7/report.md` identified cache-local directed edge-index adjacency as the next primitive.
- One lever only: expose `DiGraph::edges_ordered_indices()` and build directed Eulerian reverse adjacency from `(source_idx, target_idx)` pairs instead of borrowed node keys plus two index lookups per edge.

## Benchmark

Primary current-main same-host, interleaved final comparison after rebasing on `55db84e6d`:

```text
hyperfine --warmup 3 --runs 12 \
  'env PYTHONPATH=/data/projects/.scratch/franken_networkx-boldfalcon-current-baseline-package-55db python3 tests/artifacts/perf/20260604T-delegation-goldmine-sweep/bench_delegation_goldmines.py --case eulerian_path_directed --impl fnx --size 2000 --repeats 30' \
  'env PYTHONPATH=/data/projects/.scratch/franken_networkx-boldfalcon-current-final-package-5054 python3 tests/artifacts/perf/20260604T-delegation-goldmine-sweep/bench_delegation_goldmines.py --case eulerian_path_directed --impl fnx --size 2000 --repeats 30'
```

| Run | Mean | Median | Stddev |
| --- | ---: | ---: | ---: |
| Current main FNX (`55db84e6d`) | 0.49147367477s | 0.48547666910s | 0.03426367250s |
| Final FNX (`5054b6ef1`) | 0.44441349152s | 0.44160142060s | 0.03317319518s |

Final is 1.11x faster by mean and 1.10x faster by median against the true current-main baseline.

Initial same-host comparison before `origin/main` advanced is retained for audit in `final_compare_baseline_vs_after_hyperfine.json`:

| Run | Mean | Median | Stddev |
| --- | ---: | ---: | ---: |
| Initial baseline FNX | 0.71054222258s | 0.70630267388s | 0.04357590926s |
| Initial final FNX | 0.61977698428s | 0.61156385538s | 0.03539994839s |

The current-main direct per-call files are used as digest proof rather than the primary timing signal because the sub-2 ms samples are noisy under concurrent host load.

Score: Impact 2 x Confidence 3 / Effort 1 = 6.0, clearing the keep gate.

## Isomorphism proof

- Ordering: `edges_ordered_indices()` walks `succ_indices` rows in the same row and target order as `edges_ordered_borrowed()`, and filters through the same `edges.contains_key((u, t))` validity check. The new unit assertion locks the index sequence for duplicate merge/order cases.
- Tie-breaking: `eulerian_path_directed` still pushes each reverse adjacency entry in edge-order traversal order and still consumes `edge_pos[current]` monotonically. No candidate-edge branch or start-node policy changed.
- Node identity: the old path converted each edge endpoint back through node keys and `get_node_index`; the new path uses the already-stored indices for the same endpoints. Node insertion order and edge insertion/merge semantics are unchanged.
- Floating point: no floating-point operations in this code path.
- RNG: no random state, seed, or randomized iteration is used.
- Error behavior: directed Eulerian validation and start selection are unchanged. Edge indices come from internal graph storage that was already authoritative for the borrowed edge iterator.

## Golden output

- `current_main_baseline_direct.jsonl`: digest `55d6e89b71f957b470c6b51d788f3fd492661e6bd22d231f513fc0916bdcd45a`.
- `current_main_final_direct.jsonl`: digest `55d6e89b71f957b470c6b51d788f3fd492661e6bd22d231f513fc0916bdcd45a`.
- Current-main baseline artifact sha256: `a70c5eb8fad2171623ec7aa4dfa47cfd0d5149367240d52eeb3fc859084ce834`.
- Current-main final artifact sha256: `55e9ecec500ba796420abd81bffbb0efba569b97390bd1f1602f959f3a8394d2`.
- Earlier f1ab baseline/final direct files also record `digests_match: true` with the same digest.

## Validation

- `rch exec -- cargo check -p fnx-algorithms --all-targets`: pass.
- `rch exec -- cargo clippy -p fnx-algorithms --all-targets -- -D warnings`: pass.
- `cargo fmt -p fnx-classes -p fnx-algorithms --check`: pass.
- `cargo test -p fnx-classes row_staged_attr_edges_preserve_orders_and_duplicate_merges`: pass.
- `cargo test -p fnx-algorithms eulerian_path_directed -- --nocapture`: pass, 4 tests.
- `python3 -m pytest tests/python/test_eulerian_path_directed_parity.py tests/python/test_eulerian_conformance.py -q -k eulerian_path`: pass, 111 passed and 165 deselected.
- `git diff --check -- crates/fnx-classes/src/digraph.rs crates/fnx-algorithms/src/lib.rs tests/artifacts/perf/20260609T-eulerian-edgeindex-boldfalcon`: pass.
- `ubs $(git diff --name-only --cached)`: exit 1 due a false positive at `crates/fnx-algorithms/src/lib.rs:33593`, where UBS classifies `if new_group_id != group_of[i]` as a secret comparison. This is a graph community/group id comparison and is outside the eulerian diff. UBS also reported formatting, clippy, cargo check, test-build, cargo audit, and cargo deny clean.

## Next primitive

Profile shifted from endpoint lookup toward native traversal and output materialization. The next deeper safe-Rust primitive is a reusable edge-order index slice or pre-sized reverse adjacency path that avoids allocating a fresh ordered edge vector before every Eulerian traversal while preserving the same edge-order witness.
