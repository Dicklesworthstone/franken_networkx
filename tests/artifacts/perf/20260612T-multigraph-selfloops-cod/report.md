# br-r37-c1-5sg97 MultiGraph self-loop count

## Target

- Bead: `br-r37-c1-5sg97`
- Profile-backed hotspot: `number_of_selfloops(MultiGraph)` fell through to `sum(1 for _ in selfloop_edges(G))`, which scanned node keys, probed `has_edge(n, n)`, materialized `G[n]`, and counted parallel keys in Python.
- Baseline profile, 10k calls: 5.723s total, with 5.642s in Python `sum`, 5.513s in the generator, 2.722s in `adjacency_entries`, and 1.694s in `has_edge`.

## Lever

One lever: add native `MultiGraph::number_of_selfloops` and `MultiDiGraph::number_of_selfloops` accessors that sum the key-bucket length for `(u, u)` edge buckets, expose them as `_fnx.multigraph_number_of_selfloops_rust`, and route only `G.is_multigraph()` through that binding with the old Python path as fallback.

The clippy-only cleanup in `DiGraph::reversed` converts two index loops to iterator/enumerate form without changing row walk order.

## Benchmarks

| Gate | Before | After | Ratio |
| --- | ---: | ---: | ---: |
| MultiGraph mean, 40 samples | 0.000175450s/call | 0.000006463s/call | 27.15x |
| MultiDiGraph mean, 40 samples | 0.000171956s/call | 0.000006859s/call | 25.07x |
| rch hyperfine mean, 10 runs | 1.519299400s | 0.320893699s | 4.73x |
| cProfile total, 10k MultiGraph calls | 5.723s | 0.085s | 67.33x |

After profile: the former Python `sum(selfloop_edges(...))` stack is gone; the measured hot call is `franken_networkx._fnx.multigraph_number_of_selfloops_rust`.

## Behavior Proof

- Count semantics: NetworkX counts every parallel self-loop edge. The native path sums `edge_bucket.len()` for buckets whose endpoints are identical, exactly matching `selfloop_edges` multiplicity.
- Ordering/tie-breaking: `number_of_selfloops` returns only an integer, so no output ordering or tie-breaking is exposed. The proof harness still verifies `selfloop_edges` and `selfloop_edges(keys=True)` payloads are unchanged for MultiGraph and MultiDiGraph fixtures.
- Directedness: MultiGraph uses canonical undirected `EdgeKey`; MultiDiGraph uses directed `DirectedEdgeKey`. Both only count buckets where source/target are identical.
- Floating point: not applicable.
- RNG: benchmark/proof fixture construction uses deterministic seed `20260612`; the function under test has no RNG.
- Golden output: `after_proof.json` has `all_match=true`; FNX and NX payload digest both equal `8e86adfc96716b5d0f3676f6fea548941c09091729dc1422183924d35b5c1d99`; MultiGraph and MultiDiGraph counts are both 152.

## Gates

- Baseline and after: `rch exec -- maturin build --release --features pyo3/abi3-py310`
- Baseline and after: `rch exec -- hyperfine --warmup 2 --runs 10 ... harness_selfloops.py bench --calls 1000 --samples 5 --warmups 1`
- `rch exec -- cargo test -p fnx-classes counts_parallel_selfloops_only --lib`
- `rch exec -- cargo check -p fnx-classes --all-targets`
- `rch exec -- cargo check -p fnx-python --all-targets --features pyo3/abi3-py310`
- `rch exec -- cargo clippy -p fnx-classes --all-targets -- -D warnings`
- `rch exec -- cargo clippy -p fnx-python --all-targets --features pyo3/abi3-py310 --no-deps -- -D warnings`
- Focused Python parity: 44 passed
- `rustfmt --edition 2024 --check crates/fnx-classes/src/lib.rs crates/fnx-classes/src/digraph.rs`
- `python3 -m py_compile python/franken_networkx/__init__.py`
- `sha256sum -c tests/artifacts/perf/20260612T-multigraph-selfloops-cod/proof_files.sha256`

`rustfmt --edition 2024 --check crates/fnx-python/src/algorithms.rs` still reports unrelated pre-existing formatting drift elsewhere in that file; the new binding block is rustfmt-shaped and the crate-level clippy gate passes.

## Score

Impact 4.0 x Confidence 4.0 / Effort 1.5 = 10.67. The lever clears the required 2.0 keep threshold and beats the bead target by a wide margin.
