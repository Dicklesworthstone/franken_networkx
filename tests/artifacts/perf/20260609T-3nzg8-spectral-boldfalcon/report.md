# br-r37-c1-3nzg8 native subgraph centrality expdiag

## Target

Profile-backed target: `franken_networkx.subgraph_centrality(G)` on a native
undirected `Graph`, default `normalized=False`.

Baseline profile at n=260 showed the public FNX call spent 4.034s of 4.046s
inside `numpy.linalg.eigh`; graph-to-matrix conversion was below 1ms in the
phase profile. The lever replaces that default path with the existing safe-Rust
scaling-and-squaring matrix exponential and returns only the diagonal.

`normalized=True`, directed graphs, multigraphs, and non-native graph objects
keep the previous NumPy/eigh path and error behavior.

## One Lever

Added `fnx_algorithms::subgraph_centrality_expdiag`, exposed it through
`_fnx.subgraph_centrality_expdiag_rust`, and routed default native
`subgraph_centrality` calls to it.

No C BLAS/LAPACK/MKL/XLA linkage was added.

## Behavior Proof

Golden corpus:

- Baseline rounded corpus sha256: `e4e3d9adc21ecd86f77ca353537659674742a99e06a23b2fec342c1e2ed934fb`
- After rounded corpus sha256: `e4e3d9adc21ecd86f77ca353537659674742a99e06a23b2fec342c1e2ed934fb`
- Max relative drift vs NetworkX after: `3.278618893393505e-14`
- Conformance tolerance: `1e-6`

Isomorphism notes:

- Ordering: Rust scores are emitted in `Graph::nodes_ordered()` and the Python
  binding inserts dict items in that order, matching the old `nodelist` order.
- Tie-breaking: no graph traversal or shortest-path tie policy is involved.
- Floating point: computation changes from eigendecomposition to
  scaling-and-squaring; values are equal to the rounded golden corpus and within
  `3.3e-14` relative error vs NetworkX on the corpus.
- RNG: none used.
- Error surface: multigraph and directed guards run before the native call;
  normalized mode stays on the previous NumPy path.

## Benchmarks

Command:

```bash
VIRTUAL_ENV=/data/projects/franken_networkx/.venv PATH=/data/projects/franken_networkx/.venv/bin:$PATH rch exec -- hyperfine --warmup 2 --runs 7 \
  'python tests/artifacts/perf/20260609T-3nzg8-spectral-boldfalcon/harness_spectral.py bench --impl fnx --case subgraph --size 260 --runs 1' \
  'python tests/artifacts/perf/20260609T-3nzg8-spectral-boldfalcon/harness_spectral.py bench --impl nx --case subgraph --size 260 --runs 1'
```

Results:

- FNX baseline mean: `3.705486925s`
- FNX after mean: `0.412756362s`
- FNX speedup: `8.98x`
- Genuine NetworkX baseline mean: `6.105585480s`
- Genuine NetworkX after-run mean: `4.411727446s`
- FNX vs NetworkX before: `1.65x faster`
- FNX vs NetworkX after: `10.69x faster`

Inner warm-min check after rebuild:

- FNX: `53.601ms`
- NetworkX: `950.014ms`
- Ratio: `17.72x faster`

Score: Impact 5 x Confidence 5 / Effort 2 = 12.5, keep.

## Validation

- `rch exec -- cargo check -p fnx-algorithms -p fnx-python --all-targets` passed.
- Focused pytest passed: `23 passed in 0.86s`.
- `rch exec -- cargo clippy -p fnx-algorithms --all-targets -- -D warnings` passed.
- `rch exec -- cargo clippy -p fnx-python --lib --no-deps -- -D warnings -A clippy::collapsible-if` passed; the allow covers pre-existing collapsible-if findings outside this patch.
- `cargo fmt --check -p fnx-algorithms -p fnx-python` is blocked by pre-existing formatting drift in unrelated sections of `fnx-algorithms`, `fnx-python`, `digraph.rs`, `lib.rs`, and `readwrite.rs`; no broad rustfmt was applied.
- `ubs` on the four touched files reported broad pre-existing findings in the large files; its embedded Rust fmt/clippy/check/test-build sections were clean for the scan.
