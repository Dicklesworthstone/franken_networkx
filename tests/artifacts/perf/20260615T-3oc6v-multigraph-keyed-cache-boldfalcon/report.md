# br-r37-c1-3oc6v MultiGraph keyed EdgeView cache

## Target

Profile-backed residual after `br-r37-c1-qwqvn`: undirected
`MultiGraph.edges(keys=True)` repeatedly rebuilt every `(u, v, key)` tuple through
`PyMultiGraph._native_edge_view_list`.

Baseline profile (`baseline_profile_mg_edges_keys.txt`, 40 loops):

- Total: `0.770s`
- `_native_edge_view_list`: `0.598s`
- Python `_gen`: `0.098s`

## Lever

One lever: add a `(nodes_seq, edges_seq)` cache of immutable `(u, v, key)` tuple
objects for `data=False, keys=True, nbunch=None`.

The cache builder preserves the old public ordering rule exactly:

- node-major traversal over `nodes_ordered()`
- neighbor-row traversal over `neighbors(node)`
- canonical seen-set dedup for undirected parallel edges
- first-wins adjacency-cell display for the second endpoint
- first-wins public edge key object

## Behavior proof

Golden harness:

- Baseline `semantic_sha256`: `747b33cb617f3d8f5a51a412f08b3135ad2c9143ad82285fa35a4e0ce62fc081`
- After `semantic_sha256`: `747b33cb617f3d8f5a51a412f08b3135ad2c9143ad82285fa35a4e0ce62fc081`
- Edge output SHA: `326094764bdb6ec58a17a3c3a78064d5ef6cecf110cfb5b474b47db915221be4`
- `all_match`: `true`

Isomorphism obligations:

- Ordering: exact `list(MultiGraph.edges(keys=True))` compared with NetworkX.
- Tie-breaking: insertion order, first-wins endpoint orientation, and explicit
  key display preserved.
- Floating point: none.
- RNG: none; deterministic graph construction.
- Mutation: repeated `edges(keys=True)` before and after add/remove matched
  NetworkX.

## Benchmark

Direct harness (`bench --loops 40 --repeats 7`):

- FNX median: `16.712450ms -> 2.255468ms` per call (`7.41x`)
- FNX mean: `16.303614ms -> 2.229201ms` per call (`7.31x`)
- NetworkX after median: `3.676620ms` per call; FNX is `1.63x` faster.

rch hyperfine (`--runs 7`, 60-loop process):

- FNX mean: `1.379698s -> 0.517497s` (`2.67x`)
- FNX median: `1.373200s -> 0.511752s` (`2.68x`)
- NetworkX after mean: `0.554237s`; FNX is `1.07x` faster.

After profile (`after_profile_mg_edges_keys.txt`, 40 loops):

- Total: `0.150s`
- `_native_edge_view_list`: `0.005s`
- Python `_gen`: `0.093s`

Score: Impact `3.0` x Confidence `0.95` / Effort `1.0` = `2.85` keep.

## Validation

- `rch exec -- cargo check -p fnx-python --lib --features pyo3/abi3-py310`
- `rch exec -- cargo clippy -p fnx-python --lib --features pyo3/abi3-py310 -- -D warnings`
- `cargo fmt --package fnx-python --check`
- `git diff --check`
- Focused pytest: `19 passed`
- Inline cache-invalidation parity smoke passed.
- `ubs --only=rust crates/fnx-python/src/lib.rs crates/fnx-python/src/digraph.rs`
  exited `0`; no critical findings.
