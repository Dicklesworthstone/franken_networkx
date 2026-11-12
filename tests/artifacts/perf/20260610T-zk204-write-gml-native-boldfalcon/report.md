# br-r37-c1-zk204 - Native int/noattr write_gml

## Target

Profile-backed fallback target selected because `br ready --json` had no open perf child beads. Current `write_gml` on int-labeled no-attr `Graph` still spent its time in NetworkX's GML generator after the earlier direct-FNX writer shortcut.

Baseline cProfile for 3 writes of a deterministic 3000-node / 9000-edge graph:

- Total: `0.180 s`
- `networkx.readwrite.gml.write_gml`: `0.170 s`
- `networkx.readwrite.gml.generate_gml`: `0.088 s`
- FNX node iteration/materialization: `0.017 s`

## One Lever

Add a strict native route for exactly:

- `stringizer is None`
- `type(G) is Graph`
- plain path/file-like output, not `.gz` or `.bz2`
- integer node display objects only
- no graph, node, or edge Python attr mirrors materialized

All string labels, attrs, directed graphs, multigraphs, stringizer calls, compressed paths, views, and subclasses stay on the existing NetworkX writer path.

The native writer now emits NetworkX-compatible GML for this case: sequential node IDs in node iteration order, original int labels in `label`, and undirected edge orientation from the graph's NetworkX-style edge view order.

## Baseline

Command:

```bash
rch exec -- hyperfine --warmup 1 --runs 5 --export-json tests/artifacts/perf/20260610T-zk204-write-gml-native-boldfalcon/baseline_hyperfine_write_gml_random3000_r50.json --command-name fnx_write_gml_random3000_r50 'env PYTHONPATH=python python3 tests/artifacts/perf/20260610T-zk204-write-gml-native-boldfalcon/harness_write_gml_native.py time --impl fnx --nodes 3000 --edges 9000 --seed 1 --repeats 50' --command-name nx_write_gml_random3000_r50 'env PYTHONPATH=python python3 tests/artifacts/perf/20260610T-zk204-write-gml-native-boldfalcon/harness_write_gml_native.py time --impl nx --nodes 3000 --edges 9000 --seed 1 --repeats 50' --command-name raw_write_gml_random3000_r50 'env PYTHONPATH=python python3 tests/artifacts/perf/20260610T-zk204-write-gml-native-boldfalcon/harness_write_gml_native.py time --impl raw --nodes 3000 --edges 9000 --seed 1 --repeats 50'
```

Result:

- FNX mean: `1.178 s +/- 0.041 s`
- NetworkX mean: `1.002 s +/- 0.037 s`
- Raw native non-byte-compatible bound: `406.3 ms +/- 14.2 ms`

## After

Command:

```bash
rch exec -- hyperfine --warmup 1 --runs 5 --export-json tests/artifacts/perf/20260610T-zk204-write-gml-native-boldfalcon/after_hyperfine_write_gml_random3000_r50.json --command-name fnx_write_gml_random3000_r50 'env PYTHONPATH=python python3 tests/artifacts/perf/20260610T-zk204-write-gml-native-boldfalcon/harness_write_gml_native.py time --impl fnx --nodes 3000 --edges 9000 --seed 1 --repeats 50' --command-name nx_write_gml_random3000_r50 'env PYTHONPATH=python python3 tests/artifacts/perf/20260610T-zk204-write-gml-native-boldfalcon/harness_write_gml_native.py time --impl nx --nodes 3000 --edges 9000 --seed 1 --repeats 50' --command-name raw_write_gml_random3000_r50 'env PYTHONPATH=python python3 tests/artifacts/perf/20260610T-zk204-write-gml-native-boldfalcon/harness_write_gml_native.py time --impl raw --nodes 3000 --edges 9000 --seed 1 --repeats 50'
```

Result:

- FNX mean: `458.0 ms +/- 21.4 ms`
- NetworkX mean: `996.5 ms +/- 31.9 ms`
- Raw native writer: `378.6 ms +/- 17.4 ms`
- FNX vs baseline FNX: `2.57x` faster
- FNX vs NetworkX after: `2.18x` faster

Score: Impact `4.0` x Confidence `4.5` / Effort `2.0` = `9.0`, keep.

## Behavior Proof

Golden/reference files:

- `baseline_proof.json`
- `after_proof.json`

Parity:

- Golden SHA unchanged: `94928cdc4a1fe6bded4d6af013273b0a4311b1f9d78f04ae20e7423dff19317e`
- Cases: 9, failures: 0
- Node order: deterministic construction; byte proof covers sequential IDs and labels.
- Tie-breaking: no algorithmic ties; byte proof covers edge order and orientation.
- RNG: deterministic random-int case uses `seed=11`.
- Floating point: none; GML output is byte-for-byte text.

## Validation

- `rch exec -- cargo check -p fnx-readwrite -p fnx-python --all-targets`: passed; `rch` fell back locally because no worker was admissible.
- `cargo fmt -p fnx-readwrite --check`: passed.
- `rustfmt --check crates/fnx-python/src/readwrite.rs`: passed.
- `cargo fmt -p fnx-readwrite -p fnx-python --check`: still fails on pre-existing unrelated rustfmt drift in `crates/fnx-python/src/algorithms.rs`, `crates/fnx-python/src/digraph.rs`, and `crates/fnx-python/src/lib.rs`; this commit does not include that formatting churn.
- `rch exec -- cargo clippy -p fnx-readwrite --all-targets -- -D warnings`: passed; `rch` fell back locally because no worker was admissible.
- `rch exec -- cargo clippy -p fnx-python --lib --no-deps -- -D warnings -A clippy::collapsible-if`: passed remotely.
- `rch exec -- env PYTHONPATH=python python3 -m pytest tests/python/test_io_variants.py -k 'gml' -q`: `12 passed, 28 deselected`.
- `git diff --check`: passed.
- `timeout 240 ubs crates/fnx-readwrite/src/lib.rs crates/fnx-python/src/readwrite.rs python/franken_networkx/readwrite/__init__.py tests/python/test_io_variants.py tests/artifacts/perf/20260610T-zk204-write-gml-native-boldfalcon/harness_write_gml_native.py`: completed exit 1; UBS internal fmt/clippy/check/test-build were clean, findings were broad pre-existing/heuristic warnings in scanned files plus test-assert warnings.
