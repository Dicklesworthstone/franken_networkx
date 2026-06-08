# br-r37-c1-mexh6 - MultiGraph to_dict_of_lists Rust snapshot

## Target

Profile-backed target: `to_dict_of_lists` for exact `MultiGraph` and
`MultiDiGraph`, after the peer row-key baseline commits `62545ce86` and
`a32231146`.

Before push, this commit was rebased over `c3c07b50b` and `9d526fb67`, which
touch separate multigraph readwrite/PageRank fast paths. Final `fnx-python`
fmt/check/clippy, release install, focused pytest, golden proof, and artifact
checksum gates were rerun on the rebased tree.

The previous remote baseline reduced Python row-key overhead but still built
the final `{node: [neighbors]}` result in Python. This lever extends the
existing native `to_dict_of_lists_undirected` helper to snapshot exact
MultiGraph and MultiDiGraph adjacency rows directly in Rust/PyO3 for the
`nodelist is None` path.

## Lever

One lever only:

- Add `GraphRef::MultiUndirected` and `GraphRef::MultiDirected` handling in
  `crates/fnx-python/src/readwrite.rs::to_dict_of_lists_undirected`.
- Widen the exact-type Python fast-path gate in
  `python/franken_networkx/__init__.py::to_dict_of_lists` to include
  `MultiGraph` and `MultiDiGraph`.
- Expose `py_node_key` as `pub(crate)` for the two multigraph wrappers so the
  readwrite helper can preserve original Python node keys.

## Behavior proof

Golden SHA stayed unchanged across baseline and after:

```text
6485155e15f45c2097a8bc5e1fb68572ed27c626c9f13fcc30c156f03d2edc03
```

Case SHAs:

```text
MultiGraph:    a39dceef4c77c0b251025dbb967ddbaff70a7357bdeef7a00f99e4f2c4c38590
MultiDiGraph: 30bb3921dff84292c59fba48a9f90f184eaf6e06f7b2ffa789826c09369ab77c
```

Isomorphism:

- Ordering: iterates `nodes_ordered()` and native neighbor/successor row order,
  matching the existing row-key baseline and NetworkX proof harness.
- Tie-breaking: no graph algorithm tie-breaks are touched; only adjacency
  serialization is snapshotted.
- Floating point: no numeric arithmetic is added.
- RNG: no random state is read or written.
- Fallbacks: any `nodelist`, subclass, view, or unsupported shape still uses the
  previous Python implementation.

## Benchmark

Direct timed hot-call medians, 35 repeats:

| Case | Baseline | After | Speedup |
| --- | ---: | ---: | ---: |
| FNX MultiGraph lists | 0.0008172870147973299s | 0.00025315897073596716s | 3.23x |
| FNX MultiDiGraph lists | 0.0007664210861548781s | 0.00019997789058834314s | 3.83x |

Hyperfine process envelope, 10 runs, 200 conversions:

| Case | Baseline mean | After mean | Speedup |
| --- | ---: | ---: | ---: |
| FNX MultiGraph lists | 0.49095218564s | 0.43255363774s | 1.14x |
| FNX MultiDiGraph lists | 0.48930707504s | 0.38324685124s | 1.28x |

Post-change cProfile over 300 conversions:

```text
MultiGraph:    1201 calls in 0.089s, dominated by _fnx.to_dict_of_lists_undirected
MultiDiGraph: 1201 calls in 0.078s, dominated by _fnx.to_dict_of_lists_undirected
```

## Gates

- `cargo fmt -p fnx-python --check`
- `rch exec -- cargo check -p fnx-python --all-targets --features pyo3/abi3-py310`
- `rch exec -- cargo clippy -p fnx-python --all-targets --features pyo3/abi3-py310 -- -D warnings`
- `rch exec -- maturin develop --release --features pyo3/abi3-py310`
- `rch exec -- pytest -q tests/python/test_multigraph_to_dict_of_lists_parity.py`
- `python -m py_compile python/franken_networkx/__init__.py tests/python/test_multigraph_to_dict_of_lists_parity.py tests/artifacts/perf/20260608T-mexh6-rust-snapshot-tealspring/multigraph_adjacency_tax.py`
- `git diff --check`
- Rebase gates over `c3c07b50b`/`9d526fb67`: `cargo fmt -p fnx-python
  --check`, rch `cargo check -p fnx-python --all-targets --features
  pyo3/abi3-py310`, rch `cargo clippy -p fnx-python --all-targets --features
  pyo3/abi3-py310 -- -D warnings`, rch-wrapped release install, focused
  pytest `4 passed`, golden proof SHA unchanged, artifact checksums OK.
- `ubs crates/fnx-python/src/readwrite.rs crates/fnx-python/src/lib.rs crates/fnx-python/src/digraph.rs`:
  critical `0`, warnings are the existing broad binding-file inventory.
- `ubs tests/python/test_multigraph_to_dict_of_lists_parity.py tests/artifacts/perf/20260608T-mexh6-rust-snapshot-tealspring/multigraph_adjacency_tax.py`:
  critical `0`, warnings `0`.
- `timeout 90 ubs python/franken_networkx/__init__.py`: timed out on the
  monolithic generated-size module; covered by py_compile, focused proof,
  pytest, and Rust gates.

## Verdict

PRODUCTIVE / kept.

Score: `7.0` (`Impact 3.0 * Confidence 3.5 / Effort 1.5`).

Next target after reprofile: remaining conversion residuals in
`to_dict_of_dicts`/keydict-view materialization or the next ready
profile-tagged bead.
