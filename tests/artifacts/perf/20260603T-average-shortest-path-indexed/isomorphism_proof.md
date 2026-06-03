# br-r37-c1-ga0ow Isomorphism Proof

## Change

`average_shortest_path_length(Graph)` now runs each BFS source over
`Graph::neighbors_indices` with one reused `Vec<usize>` distance buffer and a
per-source `seen_stamp` buffer. The old implementation allocated
`Vec<Option<usize>>` per source, called `graph.neighbors(node_name)`, and
resolved each neighbor name through `graph.get_node_index`.

## Profile-Backed Target

Baseline pprof on `rch` for `ALGO=aspl N=1200 DEG=5 ITERS=3` showed
`average_shortest_path_length` in 3094/3094 inclusive samples. Under it,
`get_index_of` accounted for 2024 samples, with string hashing/equality in the
top symbols.

## Behavior Preservation

- Ordering preserved: yes. `neighbors_indices(u)` is maintained in the same
  insertion order as the public adjacency set used by `neighbors(node_name)`.
- Tie-breaking unchanged: yes. ASPL only consumes BFS distances; predecessor
  choices are not exposed. BFS discovery still visits each adjacency list in
  graph order.
- Floating-point unchanged: yes. The algorithm still computes an integer
  `total_distance`, then performs the same final
  `total_distance as f64 / (n * (n - 1)) as f64` division once.
- Integer summation order unchanged: yes. After each connected-source BFS, the
  code sums `dist` in node-index order, matching the old
  `dist.into_iter().flatten().sum()` vector order.
- Disconnected behavior unchanged: yes. A source with `reached < n` still
  returns `f64::INFINITY` before adding that source's distances.
- RNG unchanged: N/A. The algorithm has no RNG. Benchmark graph generation uses
  the same deterministic harness seed before and after.

## Golden Output

Deterministic harness:

```text
ALGO=aspl N=1200 DEG=5 DUMP=1
average_shortest_path_length	4.65893800389213197e0
```

Golden SHA-256 before and after:

```text
83225441a418589fc7b0aaaea3d1312eb018d3cccf8d71d925dcd1f8680907aa
```

The before and after golden files are byte-identical.

## Benchmark Delta

Criterion via `rch`, `cargo bench -p fnx-algorithms --bench
algorithm_benchmarks average_shortest_path_length -- --sample-size 10
--warm-up-time 1 --measurement-time 3`:

| Case | Before Mean | After Mean | Speedup |
| --- | ---: | ---: | ---: |
| grid/400 | 21.764 ms | 3.9518 ms | 5.51x |
| grid/900 | 127.36 ms | 15.841 ms | 8.04x |
| grid/1600 | 444.55 ms | 67.155 ms | 6.62x |

Perf harness via `rch`, `ALGO=aspl N=1200 DEG=5 ITERS=5`:

| Before | After | Speedup | Checksum |
| ---: | ---: | ---: | ---: |
| 339.9591 ms | 58.4076 ms | 5.82x | 23.294690 |

## Opportunity Score

Impact 5 x Confidence 5 / Effort 2 = 12.5. Keep.

## Validation

- `rch exec -- cargo fmt --package fnx-algorithms --check`: passed.
- `rch exec -- cargo check -p fnx-algorithms --lib --bin perf_harness`:
  passed.
- `rch exec -- cargo clippy -p fnx-algorithms --lib --bin perf_harness
  --no-deps -- -D warnings`: passed remotely on `vmi1293453`.
- `rch exec -- cargo test -p fnx-algorithms average_shortest_path_length
  --lib -- --nocapture`: passed, with 0 matching tests and 823 filtered out.
- `sha256sum -c golden_before_sha256.txt` and
  `sha256sum -c golden_after_sha256.txt`: passed.
- `diff -u golden_before.txt golden_after.txt`: passed.

Scoped caveats:

- Full `cargo test -p fnx-algorithms --lib` was also run remotely. It passed
  822 tests and failed one unrelated pre-existing property test,
  `tests::property_packet_005_invariants`, in multi-source Dijkstra node-order
  expectations. This ASPL lever does not touch that path.
- `ubs` over the three touched Rust files exited 1 on existing broad inventory
  findings. The single reported critical is an unrelated group-id equality
  comparison at `crates/fnx-algorithms/src/lib.rs:30837`, not this ASPL path.
