# br-r37-c1-1i2au — Native LU Current-Flow Closeness

## Target

Profile-backed target: `current_flow_closeness_centrality(..., solver="lu")` on the unweighted simple-`Graph` default path.

The existing implementation computed Python RCM ordering, built a SciPy sparse Laplacian, factorized with SuperLU, then solved one RHS per row. The shipped lever keeps Python's preconditions and RCM ordering, but routes the default unweighted LU path into the in-tree safe-Rust LU primitive with partial pivoting and a grounded reduced-Laplacian inverse.

## One Lever

Only the default `type(G) is Graph`, `weight is None`, `dtype is float`, `solver == "lu"` path routes native. Weighted, non-default dtype, `full`, `cg`, directed, multigraph, invalid solver, and disconnected cases stay on the previous Python/SciPy implementation.

## Baseline

Command:

```bash
rch exec -- hyperfine --warmup 1 --runs 7 --export-json tests/artifacts/perf/20260609T-1i2au-lu-boldfalcon/baseline_hyperfine_cfc_lu_watts240_r3.json --command-name fnx_cfc_lu_watts240_r3 'env PYTHONPATH=python python3 tests/artifacts/perf/20260609T-1i2au-lu-boldfalcon/harness_current_flow_lu.py time --func cfc --graph watts --n 240 --solver lu --impl fnx --repeats 3' --command-name nx_cfc_lu_watts240_r3 'env PYTHONPATH=python python3 tests/artifacts/perf/20260609T-1i2au-lu-boldfalcon/harness_current_flow_lu.py time --func cfc --graph watts --n 240 --solver lu --impl nx --repeats 3'
```

Result:

- FNX mean: `575.7 ms +/- 33.2 ms`
- NetworkX mean: `616.3 ms +/- 51.0 ms`
- FNX vs NetworkX: `1.07x` faster

## After

Command:

```bash
rch exec -- hyperfine --warmup 1 --runs 7 --export-json tests/artifacts/perf/20260609T-1i2au-lu-boldfalcon/after_local_hyperfine_cfc_lu_watts240_r3.json --command-name fnx_cfc_lu_watts240_r3 'env PYTHONPATH=python python3 tests/artifacts/perf/20260609T-1i2au-lu-boldfalcon/harness_current_flow_lu.py time --func cfc --graph watts --n 240 --solver lu --impl fnx --repeats 3' --command-name nx_cfc_lu_watts240_r3 'env PYTHONPATH=python python3 tests/artifacts/perf/20260609T-1i2au-lu-boldfalcon/harness_current_flow_lu.py time --func cfc --graph watts --n 240 --solver lu --impl nx --repeats 3'
```

Result:

- FNX mean: `326.7 ms +/- 16.3 ms`
- NetworkX mean: `560.8 ms +/- 31.9 ms`
- FNX vs baseline FNX: `1.76x` faster
- FNX vs NetworkX after: `1.72x` faster

Score: Impact `4.0` x Confidence `4.0` / Effort `3.0` = `5.33`, keep.

## Behavior Proof

Golden/reference files:

- `baseline_proof_cfc_lu_watts120.json`
- `after_local_proof_cfc_lu_watts120.json`
- `after_local_proof_cfc_lu_watts240.json`

Parity:

- Keys match NetworkX exactly.
- Node order: nodes inserted as `range(n)`; RCM ordering still computed by the existing Python implementation.
- Tie-breaking: no new tie-breaking policy; keyed outputs are compared after the same RCM/relabel prelude.
- RNG: deterministic graph generation; Watts-Strogatz uses `seed=37`.
- Floating point: native LU changes the exact FNX SHA relative to the former SciPy LU path, but remains inside the upstream parity envelope:
  - `n=120`: max_abs `6.59e-17`, max_rel `4.01e-15`, FNX SHA `b91d23b348c115e1ed2a8b1a5a0cd0e93d9a2df9adce173e8ca2c91d870070c0`, NetworkX SHA `4ccfe3704341a01f09ba4126e59a053fc987cfaaccd602af37498491bf2a87e3`
  - `n=240`: max_abs `2.60e-17`, max_rel `3.57e-15`, FNX SHA `51d892b30d951f39b5d400f2f5bfc6c1f1c59f8aac507271e497d43eae534538`, NetworkX SHA `27e00e79bfeb80ff770f4754d62f88429b224af42a13a7cabfa6cb6ab696c42f`

## Validation

- `rch exec -- cargo check -p fnx-algorithms -p fnx-python --all-targets`: passed. Pre-existing `fnx-generators` warnings surfaced.
- `rch exec -- cargo clippy -p fnx-algorithms --all-targets -- -D warnings`: passed.
- `rch exec -- cargo clippy -p fnx-python --lib --no-deps -- -D warnings -A clippy::collapsible-if`: passed.
- `rch exec -- python3 -m pytest tests/python/test_centrality_extensions_parity.py::test_current_flow_closeness_centrality_matches_networkx_without_fallback tests/python/test_centrality_extensions_parity.py::test_current_flow_closeness_centrality_error_contract_matches_networkx tests/python/test_centrality_conformance_matrix.py::test_current_flow_closeness_centrality_is_native_not_nx_delegate tests/python/test_current_flow_closeness_float_type_parity.py -q`: `8 passed`.
- `git diff --check`: passed.
- `cargo fmt --check -p fnx-algorithms -p fnx-python`: still fails on pre-existing unrelated rustfmt drift; this patch's rustfmt complaint was fixed manually.
- `timeout 240 ubs crates/fnx-algorithms/src/lib.rs crates/fnx-python/src/algorithms.rs`: completed; broad pre-existing findings remain, with UBS internal fmt/clippy/check/test-build clean.
- `timeout 180 ubs python/franken_networkx/__init__.py tests/artifacts/perf/20260609T-1i2au-lu-boldfalcon/harness_current_flow_lu.py`: timed out before emitting findings.
