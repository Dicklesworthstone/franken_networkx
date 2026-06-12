# br-r37-c1-04z53.75 random_regular_graph direct builder

## Target

- Bead: `br-r37-c1-04z53.75`
- Profile-backed hotspot: after `br-r37-c1-04z53.74`, `random_regular_graph(8, 1500, seed=12345)` still spent 0.662s/160 calls in Python `add_edges_from`, with 0.494s in `_try_add_edges_from_batch`.
- Required golden digest: `cac80aef6f181434007d93ef151d69b54867433c4b54c30c76a3c24f3e55bf24`

## Lever

One lever: for the exact native edge-pyset path only, build the final `Graph` in Rust instead of returning a `PySet` to Python and routing it through `Graph.add_edges_from`.

The wrapper still requires exact `int` `d`, exact `int` `n`, exact `int` seed, default `create_using`, and `n * d <= 1_000_000`. Other inputs keep the previous Python/NetworkX-compatible path.

## Benchmarks

| Gate | Before | After | Ratio |
| --- | ---: | ---: | ---: |
| inner mean, 40 samples | 0.007010074s | 0.004443118s | 1.58x |
| inner median, 40 samples | 0.006502602s | 0.004210387s | 1.54x |
| rch hyperfine mean, 10 runs | 0.767630320s | 0.537500660s | 1.43x |
| rch hyperfine median, 10 runs | 0.765131017s | 0.532788364s | 1.44x |
| cProfile total, 160 builds | 1.133s | 0.462s | 2.45x |

The after profile has 801 calls in 0.462s. The former Python `add_edges_from` and `_try_add_edges_from_batch` stack is gone; sampled time is in `franken_networkx._fnx.random_regular_graph_pyset_order`.

## Behavior Proof

- Ordering and tie-breaking: the Rust builder constructs the same CPython `PySet` of `(min(u, v), max(u, v))` edge tuples as the previous kept path, then iterates that real set. `extend_edges_unrecorded` receives edges in the same CPython set iteration order that Python `Graph.add_edges_from(edges)` observed before this lever.
- Node order: the native builder pre-creates nodes `0..n-1`, matching `empty_graph(n, create_using=Graph)`. It sets `lazy_int_node_stop = n`, preserving exact-int node materialization semantics.
- RNG: edge generation still uses `fnx_generators::random_regular_edge_insertion_order(d, n, seed)`, the same state machine as `_rust_random_regular_edges_pyset`. The fast path is still guarded to exact integer seeds; non-exact seed forms fall back.
- Floating point: not applicable.
- Generalization boundary: this does not touch generic node keys, `create_using`, non-default graph types, non-int `d`/`n`, or broad `add_edges_from`; no adversarial hash-equal-node proof is required for this exact-int-only path.
- Golden target proof: `after_proof_random.json` has `all_match=true`, FNX/NX digest `cac80aef6f181434007d93ef151d69b54867433c4b54c30c76a3c24f3e55bf24`, 1500 nodes, 6000 edges.
- Broad generator proof: `after_proof_all_generators.json` has `all_match=true` for the nine generator scenarios in the shared harness.

## Gates

- `rch exec -- maturin build --release --features pyo3/abi3-py310`
- `rch exec -- hyperfine --warmup 3 --runs 10 ... random_regular_8_1500`
- Focused Python parity: 29 passed
- `rch exec -- cargo check -p fnx-python --all-targets --features pyo3/abi3-py310`
- `rch exec -- cargo test -p fnx-generators random_regular_python_edge_insertion_order_matches_fixture --lib`
- `rch exec -- cargo clippy -p fnx-python --all-targets --features pyo3/abi3-py310 --no-deps -- -D warnings`
- `rustfmt --edition 2024 --check crates/fnx-python/src/generators.rs`
- `git diff --check -- crates/fnx-python/src/generators.rs crates/fnx-python/src/lib.rs crates/fnx-python/src/digraph.rs python/franken_networkx/__init__.py python/franken_networkx/_fnx.pyi tests/artifacts/perf/20260612T-rrg-direct-builder-cod`
- `ubs crates/fnx-python/src/generators.rs crates/fnx-python/src/lib.rs crates/fnx-python/src/digraph.rs python/franken_networkx/_fnx.pyi`
- `python3 -m py_compile python/franken_networkx/__init__.py`
- `sha256sum -c tests/artifacts/perf/20260612T-rrg-direct-builder-cod/proof_files.sha256`

Whole-crate formatting remains blocked by pre-existing drift outside this lever; the touched generator Rust file passes targeted rustfmt. UBS over `python/franken_networkx/__init__.py` was interrupted after more than ten minutes of the Python scanner consuming one CPU with no output; syntax and behavior for that wrapper are covered by `py_compile`, focused parity tests, and the golden proof harness.

## Score

Impact 4.0 x Confidence 4.0 / Effort 2.0 = 8.0. The lever clears the required 2.0 keep threshold and beats the bead's >=1.25x same-worker target.
