# br-r37-c1-kpsns - two-degenerate k_components residual certificate

## Target

Profile-backed follow-up after `br-r37-c1-jfsyo`. The residual bundle showed
`chorded_cycle/16` still using NetworkX's Moody-White / Kanevsky
`all_node_cuts` path:

- FNX direct mean: `644.04 ms`
- Genuine NX direct mean: `625.20 ms`
- FNX hyperfine mean: `1.063 s`
- Profile: `all_node_cuts` + `dag.antichains` dominated; flow itself was small.

## Lever

Add a guarded simple-`Graph` certificate for default `k_components` when every
connected component is:

1. biconnected;
2. 2-degenerate, proven by peel order; and
3. self-loop free.

Proof obligation: a 3-connected graph has minimum degree at least 3. A
2-degenerate graph has no induced subgraph with minimum degree 3, so it cannot
contain any k-component for `k >= 3`. If the whole component is biconnected, its
lattice is exactly `{2: component, 1: component}`. Any failed certificate and
any custom `flow_func` delegates unchanged.

## Baseline

Baseline was taken from a clean detached worktree at `c8a8c82cf` before source
edits, with the baseline extension installed into the same venv.

Direct timings, 3 samples:

| Case | Baseline FNX | Genuine NX | Result SHA |
| --- | ---: | ---: | --- |
| `chorded_cycle/12` | `53.11 ms` | `46.88 ms` | `0994c6151bd3f809184ac5a6977abcd76e90e7d83a0e10599b98d2ededc027d8` |
| `chorded_cycle/16` | `657.96 ms` | `665.80 ms` | `f546ac56e7b627d76539490728c9bd9f3f163ab8907fb3b223990a3c36db7b5d` |

Hyperfine on `chorded_cycle/16`:

| Command | Mean | Median |
| --- | ---: | ---: |
| FNX public `k_components` | `967.9 ms` | `962.7 ms` |
| Genuine NX `orig_func` | `1.013 s` | `1.023 s` |

Profile baseline: FNX spent `1.817 s` in `_call_networkx_for_parity`, with
NetworkX `all_node_cuts` taking `1.807 s` cumulative and `dag.antichains`
taking `987 ms` cumulative.

## After

Direct timings, 3 samples:

| Case | Baseline FNX | After FNX | Speedup |
| --- | ---: | ---: | ---: |
| `chorded_cycle/12` | `53.11 ms` | `0.266 ms` | `199.5x` |
| `chorded_cycle/16` | `657.96 ms` | `0.224 ms` | `2939x` |

Hyperfine on `chorded_cycle/16`:

| Command | Mean | Median |
| --- | ---: | ---: |
| FNX public `k_components` | `296.0 ms` | `296.2 ms` |
| Genuine NX `orig_func` | `978.6 ms` | `975.7 ms` |

Process-level speedup: `967.9 ms -> 296.0 ms`, `3.27x` self and `3.31x`
faster than genuine NetworkX in the same command harness.

After profile: `1424` calls in about `1 ms`; the residual
`_call_networkx_for_parity` / `all_node_cuts` stack is gone for accepted cases.

## Proof

- Baseline proof SHA: `89f371439172e4ae1491285d34d982a64ddad2c904edd070f893326a425ad437`
- After proof SHA: `d5397f273ab25206f23db86538fb9fab1dd5c40e3f927525951c01be7b9772f0`
- `sha256sum -c proof_files.sha256`: passed
- Focused pytest: `39 passed, 49 deselected`

Isomorphism notes:

- Ordering preserved: proof records `k` insertion order and component order.
- Tie-breaking unchanged: accepted cases have one maximal k=2 component per
  connected component; `circular_ladder_graph(6)` rejects and delegates.
- Floating point: N/A.
- RNG: N/A.
- Custom `flow_func`: delegates and raises the same sentinel as genuine
  NetworkX.

## Gates

- `git diff --check`: passed.
- `py_compile`: passed for wrapper, focused tests, and harness.
- Focused pytest: passed.
- `rch exec -- cargo check -p fnx-python --all-targets --features pyo3/abi3-py310`: passed on `ovh-a`.
- `rch exec -- cargo clippy -p fnx-python --all-targets --features pyo3/abi3-py310 -- -D warnings`: blocked by pre-existing `fnx-generators` unused-must-use warnings at `crates/fnx-generators/src/lib.rs:538,621,667,6060,6600`.
- `cargo fmt -p fnx-python --check`: blocked by pre-existing formatting drift in Rust files outside this Python-only patch.
- UBS: broad scan including the large Python wrapper timed out after 240s without emitted findings; focused scan of the harness/report/test subset completed with 0 critical and 0 warning findings.

## Score

Impact `5` x Confidence `5` / Effort `2` = `12.5`.

## Reprofile

The accepted 2-degenerate family no longer reaches `all_node_cuts`. The next
deeper residual is true 3-core / SPQR cohesive-blocking where 2-degeneracy
fails, starting with `circular_ladder_graph` and paired-clique bridge variants.
