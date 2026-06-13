# br-r37-c1-pdn5j results

## Target

- Residual hotspot: simple undirected `is_eulerian` on dense complete graphs.
- Profile-backed source: `tests/artifacts/perf/20260612T-euldense-cc/proof.json` reported K601 at ~3.14x slower than NetworkX after the prior dense-degree lever.
- Fresh baseline/profile confirmed Python degree-view iteration and self-loop scan dominated the fnx path before native connectivity.

## Lever

One lever only: route exact `Graph` inputs through `_fnx.is_eulerian`, and make the native simple-Graph path check degree parity directly from adjacency row lengths plus the NetworkX self-loop extra contribution before calling the existing native `is_connected`.

The directed, multigraph, and fallback paths are unchanged. No unsafe code and no external BLAS/C/native dependency were added.

## Baseline

Built via:

```bash
VIRTUAL_ENV=/data/projects/franken_networkx/.venv PATH=/data/projects/franken_networkx/.venv/bin:$PATH CARGO_TARGET_DIR=/data/tmp/fnx-pdn5j-baseline-target rch exec -- maturin develop --release --features pyo3/abi3-py310
```

Direct loop, `complete_601`, 500 loops x 15 repeats:

- fnx mean: `0.0002038333981986701s`
- fnx median: `0.0001983565889968304s`
- fnx min: `0.00019056323599943425s`
- NetworkX mean: `0.0001227726615354186s`
- NetworkX median: `0.00011919425100495574s`
- NetworkX min: `0.00011425823099853005s`

Hyperfine full command:

- fnx mean: `0.5544107113s`
- NetworkX mean: `0.5058850516400002s`

Baseline cProfile, 1000 fnx calls:

- total: `0.260s`
- `franken_networkx/__init__.py:is_eulerian`: `0.258s`
- Python degree parity `all(...)`: `0.086s`
- Python degree generator: `0.052s`
- `number_of_selfloops` / native self-loop scan: `0.040s`
- native `is_connected`: `0.003s`

## Candidate

Built via:

```bash
VIRTUAL_ENV=/data/projects/franken_networkx/.venv PATH=/data/projects/franken_networkx/.venv/bin:$PATH CARGO_TARGET_DIR=/data/tmp/fnx-pdn5j-candidate-target rch exec -- maturin develop --release --features pyo3/abi3-py310
```

Direct loop, `complete_601`, 500 loops x 15 repeats:

- fnx mean: `0.000014061985666436764s`
- fnx median: `0.000013249616997200064s`
- fnx min: `0.00001314601999183651s`

Hyperfine full command:

- fnx mean: `0.31540503728s`

Candidate cProfile, 1000 fnx calls:

- total: `0.015s`
- native `_fnx.is_eulerian`: `0.013s`
- Python degree generator and self-loop scan no longer appear in the hot path.

## Delta

- Direct fnx self-speedup: `14.50x`
- Hyperfine full-command self-speedup: `1.76x`
- Candidate direct mean vs NetworkX direct mean: `0.115x` of NetworkX time.
- Score: Impact `4` x Confidence `5` / Effort `1` = `20.0`.

The lever clears the `Score >= 2.0` keep rule.

## Isomorphism proof

- Ordering: scalar boolean or exception output only; no iterable order is exposed.
- Tie-breaking: none.
- Floating point: none.
- RNG: none.
- Degree semantics: native simple-Graph route computes `row_degree + self_loop_extra`, preserving NetworkX's +2 self-loop degree contribution because the adjacency row already contains the self-loop neighbor once and the integer self-loop probe supplies the second count.
- Short-circuit semantics: parity is tested before connectivity, matching NetworkX's `all(d % 2 == 0 ...) and is_connected(G)` order.
- Directed semantics: unchanged existing directed native path.
- Multigraph semantics: unchanged Python degree-view parity path, because simple graph conversion collapses parallel edges.
- Null/single/self-loop/disconnected/dense/directed parity: covered by golden cases.

Golden output SHA:

- baseline harness SHA: `f6bbb72475f861ccfffd406ce2b79671ee4a93139888155add17b3a4f0360694`
- candidate harness SHA: `f6bbb72475f861ccfffd406ce2b79671ee4a93139888155add17b3a4f0360694`
- file checks: `sha256sum -c golden_checksums.txt` passed.

## Gates

- `rch exec -- /data/projects/franken_networkx/.venv/bin/pytest tests/python/test_eulerian_conformance.py tests/python/test_self_loop_core_eulerian_parity.py tests/python/test_euler_triad_hierarchy_parity.py -q`: `283 passed in 0.76s`
- `rch exec -- cargo check -p fnx-python --lib`: passed.
- `/data/projects/franken_networkx/.venv/bin/python -m py_compile python/franken_networkx/__init__.py tests/artifacts/perf/20260613T-pdn5j-is-eulerian-boldfalcon/is_eulerian_harness.py`: passed.
- `git diff --check`: passed.
- `rustfmt --edition 2024 --check crates/fnx-python/src/algorithms.rs`: blocked by pre-existing formatting drift in unrelated hunks of `algorithms.rs`; the touched hunk matches rustfmt's suggested shape.
- `rch exec -- cargo clippy -p fnx-python --lib -- -D warnings`: blocked before the touched crate by pre-existing `fnx-generators` `unused_must_use` errors at `crates/fnx-generators/src/lib.rs:538`, `621`, `666`, `6218`, and `6758`.
- `ubs python/franken_networkx/__init__.py crates/fnx-python/src/algorithms.rs tests/artifacts/perf/20260613T-pdn5j-is-eulerian-boldfalcon/is_eulerian_harness.py`: timed out after the Rust phase completed; stopped the diagnostic process group only. Follow-up clippy blocker filed as `br-r37-c1-sp6z3`.
